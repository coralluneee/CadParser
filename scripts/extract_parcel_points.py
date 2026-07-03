#!/usr/bin/env python3
import argparse
import csv
import json
import re
from pathlib import Path


def normalize_cadnum(value):
    return re.sub(r"\D", "", value or "")


def signed_area(points):
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return total / 2.0


def exterior_ring(geometry):
    geom_type = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if geom_type == "Polygon":
        if not coords:
            raise ValueError("Polygon has no rings")
        return coords[0]
    if geom_type == "MultiPolygon":
        best = None
        best_area = -1.0
        for polygon in coords:
            if not polygon:
                continue
            ring = polygon[0]
            area = abs(signed_area(ring))
            if area > best_area:
                best = ring
                best_area = area
        if best is None:
            raise ValueError("MultiPolygon has no exterior rings")
        return best
    raise ValueError(f"Unsupported geometry type: {geom_type}")


def find_code_by_csv(data_dir, cadnum):
    for csv_path in sorted(data_dir.glob("parcels_*.csv")):
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if normalize_cadnum(row.get("kad_nomer")) == cadnum:
                    return csv_path.stem.replace("parcels_", ""), row
    return None, None


def find_feature(geojson_path, cadnum, gid=None):
    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        if gid and str(props.get("gid")) != str(gid):
            continue
        if normalize_cadnum(props.get("kad_nomer")) == cadnum:
            return feature
    return None


def write_points_csv(path, ring, relative):
    points = list(ring)
    if len(points) > 1 and points[0][:2] == points[-1][:2]:
        points = points[:-1]
    if len(points) < 3:
        raise ValueError("Parcel boundary has fewer than 3 points")

    base_x = points[0][0] if relative else 0.0
    base_y = points[0][1] if relative else 0.0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["Point", "X", "Y"])
        for index, point in enumerate(points, start=1):
            writer.writerow([index, f"{point[0] - base_x:.4f}", f"{point[1] - base_y:.4f}"])
    return len(points)


def parse_args():
    parser = argparse.ArgumentParser(description="Extract one parcel boundary to Revit CSV points.")
    parser.add_argument("cadnum", help="Cadastral number, e.g. 020361555335")
    parser.add_argument("--data", default="data", help="Folder with parcels_*.geojson and parcels_*.csv")
    parser.add_argument("--out", help="Output CSV path")
    parser.add_argument("--relative", action="store_true", help="Subtract first point and write local coordinates")
    return parser.parse_args()


def main():
    args = parse_args()
    cadnum = normalize_cadnum(args.cadnum)
    if not cadnum:
        raise SystemExit("Empty cadastral number")

    data_dir = Path(args.data).resolve()
    code, row = find_code_by_csv(data_dir, cadnum)
    if not code:
        raise SystemExit(f"Parcel {cadnum} was not found in {data_dir}")

    geojson_path = data_dir / f"parcels_{code}.geojson"
    feature = find_feature(geojson_path, cadnum, row.get("gid") if row else None)
    if feature is None:
        raise SystemExit(f"Parcel {cadnum} was found in CSV but not in {geojson_path}")

    out_path = Path(args.out) if args.out else data_dir / f"parcel_{cadnum}_points.csv"
    ring = exterior_ring(feature.get("geometry") or {})
    point_count = write_points_csv(out_path.resolve(), ring, args.relative)
    props = feature.get("properties") or {}
    print(f"Saved {point_count} points: {out_path.resolve()}")
    print(f"District: {props.get('district_code')} {props.get('district_name')}")
    print(f"Address: {props.get('address_ru')}")
    print(f"Area: {props.get('shape_area')} sq.m")


if __name__ == "__main__":
    main()
