#!/usr/bin/env python3
import argparse
import csv
import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


REST_URL = "https://map.gov4c.kz/egkn/rest"
WFS_URL = "https://map.gov4c.kz/geoserver/wfs"
REFERER = "https://map.gov4c.kz/egkn/"

DEFAULT_CODES = ["02036", "02040", "02034"]
MIN_FIELDS = [
    "geom",
    "gid",
    "district_id",
    "kad_nomer",
    "address_ru",
    "shape_area",
    "squ",
    "land_id",
    "rka",
]


def log(message):
    print(message, flush=True)


def request_json(url, method="GET", retries=3, timeout=120):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                method=method,
                headers={
                    "Accept": "application/json",
                    "Referer": REFERER,
                    "User-Agent": "Mozilla/5.0 parcel-parser/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read()
            return json.loads(body.decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"Request failed after {retries} attempts: {url}") from last_error


def fetch_aktobe_districts():
    data = request_json(f"{REST_URL}/map/districts?lang=ru")
    region = next((item for item in data if item.get("code") == "02"), None)
    if not region:
        raise RuntimeError("Region code 02 was not found in /map/districts")
    return region["districts"]


def normalize_code(code):
    code = re.sub(r"\D", "", code)
    if len(code) == 3:
        return "02" + code
    if len(code) != 5:
        raise ValueError(f"District code must look like 02036 or 036: {code}")
    return code


def webmerc_to_lonlat(x, y):
    radius = 6378137.0
    lon = math.degrees(x / radius)
    lat = math.degrees(2 * math.atan(math.exp(y / radius)) - math.pi / 2)
    return lon, lat


def lonlat_to_utm(lon, lat, zone):
    # WGS84 / UTM north, EPSG:326xx. Aktobe districts use EPSG:32640/32641.
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    k0 = 0.9996
    lon0 = math.radians(zone * 6 - 183)
    phi = math.radians(lat)
    lam = math.radians(lon)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)

    n = a / math.sqrt(1 - e2 * sin_phi * sin_phi)
    t = math.tan(phi) ** 2
    c = ep2 * cos_phi * cos_phi
    aa = cos_phi * (lam - lon0)
    m = a * (
        (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * phi)
        + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * phi)
        - (35 * e2**3 / 3072) * math.sin(6 * phi)
    )

    easting = k0 * n * (
        aa
        + (1 - t + c) * aa**3 / 6
        + (5 - 18 * t + t**2 + 72 * c - 58 * ep2) * aa**5 / 120
    ) + 500000
    northing = k0 * (
        m
        + n
        * math.tan(phi)
        * (
            aa**2 / 2
            + (5 - t + 9 * c + 4 * c**2) * aa**4 / 24
            + (61 - 58 * t + t**2 + 600 * c - 330 * ep2) * aa**6 / 720
        )
    )
    if lat < 0:
        northing += 10000000
    return easting, northing


def wkt_bbox_to_local_srs(wkt, srs, pad=500):
    if not str(srs).startswith("326"):
        raise RuntimeError(f"Only WGS84 UTM north EPSG:326xx is supported, got EPSG:{srs}")
    zone = int(str(srs)[-2:])
    nums = list(map(float, re.findall(r"-?\d+(?:\.\d+)?", wkt)))
    if len(nums) < 4:
        raise RuntimeError("District geometry does not contain enough coordinates")
    points = []
    for x, y in zip(nums[0::2], nums[1::2]):
        lon, lat = webmerc_to_lonlat(x, y)
        points.append(lonlat_to_utm(lon, lat, zone))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


def district_label(district):
    return f"{district.get('regionCode')}{district.get('code')} {district.get('nameRu')}"


def fetch_district_geometry(district):
    rn_code = district.get("rn_code")
    if not rn_code:
        raise RuntimeError(f"No rn_code for district {district_label(district)}")
    url = f"{REST_URL}/map/district?rnCode={urllib.parse.quote(str(rn_code))}"
    data = request_json(url)
    if not data.get("geom"):
        raise RuntimeError(f"No geometry returned for {district_label(district)}")
    return data


def build_wfs_url(district, bbox, start_index, page_size, fields):
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typename": "egkn:u_view",
        "outputFormat": "application/json",
        "srsname": f"EPSG:{district['srs']}",
        "bbox": ",".join(f"{v:.3f}" for v in bbox) + f",EPSG:{district['srs']}",
        "count": str(page_size),
        "sortBy": "gid",
        "viewparams": f"district_id:{district['id']}",
    }
    if start_index:
        params["startIndex"] = str(start_index)
    if fields != "all":
        params["propertyName"] = ",".join(MIN_FIELDS)
    return WFS_URL + "?" + urllib.parse.urlencode(params, safe=":,")


def write_geojson_header(handle, district, bbox, fields):
    metadata = {
        "source": "Public EGKN cadastral map",
        "source_wfs": WFS_URL,
        "layer": "egkn:u_view",
        "district_code": district["regionCode"] + district["code"],
        "district_name": district.get("nameRu"),
        "district_id": district.get("id"),
        "rn_code": district.get("rn_code"),
        "srs": f"EPSG:{district['srs']}",
        "bbox": [round(v, 3) for v in bbox],
        "fields": fields if fields == "all" else MIN_FIELDS,
    }
    handle.write('{"type":"FeatureCollection"')
    handle.write(',"name":"parcels_%s"' % metadata["district_code"])
    handle.write(',"metadata":')
    json.dump(metadata, handle, ensure_ascii=False)
    handle.write(',"features":[')


def clean_feature(feature, district):
    props = feature.setdefault("properties", {})
    props["district_code"] = district["regionCode"] + district["code"]
    props["district_name"] = district.get("nameRu")
    props["source_srs"] = f"EPSG:{district['srs']}"
    return feature


def csv_row(feature):
    props = feature.get("properties") or {}
    return {
        "gid": props.get("gid"),
        "district_code": props.get("district_code"),
        "district_name": props.get("district_name"),
        "kad_nomer": props.get("kad_nomer"),
        "address_ru": props.get("address_ru"),
        "shape_area": props.get("shape_area"),
        "squ": props.get("squ"),
        "land_id": props.get("land_id"),
        "rka": props.get("rka"),
        "source_srs": props.get("source_srs"),
    }


def fetch_parcels_for_district(district, out_dir, page_size, limit, fields, dry_run):
    code = district["regionCode"] + district["code"]
    log(f"[{code}] district: {district_label(district)}")
    district_geom = fetch_district_geometry(district)
    bbox = wkt_bbox_to_local_srs(district_geom["geom"], district["srs"])
    log(f"[{code}] bbox EPSG:{district['srs']}: {', '.join(f'{v:.3f}' for v in bbox)}")

    first_url = build_wfs_url(district, bbox, 0, 1, fields)
    first_page = request_json(first_url)
    total = int(first_page.get("numberMatched") or first_page.get("totalFeatures") or 0)
    if limit:
        total_to_fetch = min(total, limit)
    else:
        total_to_fetch = total
    log(f"[{code}] matched: {total}; fetching: {total_to_fetch}")

    summary = {
        "district": district,
        "srs": f"EPSG:{district['srs']}",
        "bbox": [round(v, 3) for v in bbox],
        "matched": total,
        "requested": total_to_fetch,
        "fields": fields if fields == "all" else MIN_FIELDS,
        "dry_run": dry_run,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"summary_{code}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if dry_run or total_to_fetch == 0:
        return summary

    geojson_path = out_dir / f"parcels_{code}.geojson"
    csv_path = out_dir / f"parcels_{code}.csv"
    csv_fields = [
        "gid",
        "district_code",
        "district_name",
        "kad_nomer",
        "address_ru",
        "shape_area",
        "squ",
        "land_id",
        "rka",
        "source_srs",
    ]

    written = 0
    seen = set()
    with geojson_path.open("w", encoding="utf-8", newline="") as gj, csv_path.open(
        "w", encoding="utf-8-sig", newline=""
    ) as cf:
        write_geojson_header(gj, district, bbox, fields)
        writer = csv.DictWriter(cf, fieldnames=csv_fields)
        writer.writeheader()
        first_feature = True

        for start in range(0, total_to_fetch, page_size):
            count = min(page_size, total_to_fetch - start)
            url = build_wfs_url(district, bbox, start, count, fields)
            page = request_json(url)
            features = page.get("features", [])
            if not features:
                log(f"[{code}] empty page at startIndex={start}; stopping")
                break
            for feature in features:
                props = feature.get("properties") or {}
                gid = props.get("gid")
                if gid in seen:
                    continue
                seen.add(gid)
                feature = clean_feature(feature, district)
                if not first_feature:
                    gj.write(",")
                json.dump(feature, gj, ensure_ascii=False, separators=(",", ":"))
                writer.writerow(csv_row(feature))
                first_feature = False
                written += 1
            log(f"[{code}] {written}/{total_to_fetch}")
            if written >= total_to_fetch:
                break
        gj.write("]}")

    summary["written"] = written
    summary["geojson"] = str(geojson_path)
    summary["csv"] = str(csv_path)
    (out_dir / f"summary_{code}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def parse_args():
    parser = argparse.ArgumentParser(description="Download EGKN parcel boundaries for Aktobe districts.")
    parser.add_argument("--codes", nargs="*", default=DEFAULT_CODES, help="District codes, e.g. 02036 02040 02034")
    parser.add_argument("--all-aktobe", action="store_true", help="Download all districts in Aktobe region code 02")
    parser.add_argument("--out", default="data", help="Output directory")
    parser.add_argument("--page-size", type=int, default=5000, help="WFS page size")
    parser.add_argument("--limit", type=int, default=0, help="Limit features per district for testing")
    parser.add_argument("--fields", choices=["minimal", "all"], default="minimal", help="Attribute set to save")
    parser.add_argument("--dry-run", action="store_true", help="Only resolve districts and counts")
    return parser.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out).resolve()
    districts = fetch_aktobe_districts()
    code_map = {d["regionCode"] + d["code"]: d for d in districts}
    codes = sorted(code_map) if args.all_aktobe else [normalize_code(c) for c in args.codes]
    missing = [code for code in codes if code not in code_map]
    if missing:
        raise SystemExit(f"Codes not found in Aktobe region: {', '.join(missing)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "aktobe_districts.json").write_text(
        json.dumps(districts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summaries = []
    for code in codes:
        summaries.append(
            fetch_parcels_for_district(
                code_map[code],
                out_dir,
                args.page_size,
                args.limit,
                args.fields,
                args.dry_run,
            )
        )

    (out_dir / "summary_all.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(f"Done. Output: {out_dir}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("Interrupted")
