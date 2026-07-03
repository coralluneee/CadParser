#!/usr/bin/env python3
import argparse
import math
import re
from pathlib import Path

from extract_parcel_points import exterior_ring, find_code_by_csv, find_feature, normalize_cadnum


def clean_points(ring, relative=True):
    points = [(float(p[0]), float(p[1])) for p in ring]
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        raise ValueError("Parcel boundary has fewer than 3 points")
    if relative:
        base_x, base_y = points[0]
        points = [(x - base_x, y - base_y) for x, y in points]
    return points


def polygon_area(points):
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return abs(total / 2.0)


def polygon_perimeter(points):
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += math.hypot(point[0] - nxt[0], point[1] - nxt[1])
    return total


def bounds_center(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0


def dxf_pair(code, value):
    return f"{code}\n{value}\n"


def write_dxf(path, points, cadnum, area, perimeter, include_text=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    cx, cy = bounds_center(points)
    text_height = max(1.8, min(5.0, math.sqrt(max(area, 1.0)) / 10.0))
    cadnum = str(cadnum).encode("ascii", "replace").decode("ascii")
    label = f"KN {cadnum}  S={area:.2f} m2  P={perimeter:.2f} m"

    chunks = []
    chunks.append(dxf_pair(0, "SECTION"))
    chunks.append(dxf_pair(2, "HEADER"))
    chunks.append(dxf_pair(9, "$ACADVER"))
    chunks.append(dxf_pair(1, "AC1009"))
    chunks.append(dxf_pair(9, "$INSUNITS"))
    chunks.append(dxf_pair(70, 6))
    chunks.append(dxf_pair(0, "ENDSEC"))

    chunks.append(dxf_pair(0, "SECTION"))
    chunks.append(dxf_pair(2, "TABLES"))
    chunks.append(dxf_pair(0, "TABLE"))
    chunks.append(dxf_pair(2, "LTYPE"))
    chunks.append(dxf_pair(70, 1))
    chunks.append(dxf_pair(0, "LTYPE"))
    chunks.append(dxf_pair(2, "CONTINUOUS"))
    chunks.append(dxf_pair(70, 0))
    chunks.append(dxf_pair(3, "Solid line"))
    chunks.append(dxf_pair(72, 65))
    chunks.append(dxf_pair(73, 0))
    chunks.append(dxf_pair(40, "0.0"))
    chunks.append(dxf_pair(0, "ENDTAB"))
    chunks.append(dxf_pair(0, "TABLE"))
    chunks.append(dxf_pair(2, "LAYER"))
    chunks.append(dxf_pair(70, 2 if include_text else 1))
    chunks.append(dxf_pair(0, "LAYER"))
    chunks.append(dxf_pair(2, "0"))
    chunks.append(dxf_pair(70, 0))
    chunks.append(dxf_pair(62, 7))
    chunks.append(dxf_pair(6, "CONTINUOUS"))
    layer_defs = [("EP_BOUNDARY", 1)]
    if include_text:
        layer_defs.append(("EP_TEXT", 7))
    for layer_name, color in layer_defs:
        chunks.append(dxf_pair(0, "LAYER"))
        chunks.append(dxf_pair(2, layer_name))
        chunks.append(dxf_pair(70, 0))
        chunks.append(dxf_pair(62, color))
        chunks.append(dxf_pair(6, "CONTINUOUS"))
    chunks.append(dxf_pair(0, "ENDTAB"))
    if include_text:
        chunks.append(dxf_pair(0, "TABLE"))
        chunks.append(dxf_pair(2, "STYLE"))
        chunks.append(dxf_pair(70, 1))
        chunks.append(dxf_pair(0, "STYLE"))
        chunks.append(dxf_pair(2, "STANDARD"))
        chunks.append(dxf_pair(70, 0))
        chunks.append(dxf_pair(40, "0.0"))
        chunks.append(dxf_pair(41, "1.0"))
        chunks.append(dxf_pair(50, "0.0"))
        chunks.append(dxf_pair(71, 0))
        chunks.append(dxf_pair(42, "2.5"))
        chunks.append(dxf_pair(3, "txt"))
        chunks.append(dxf_pair(4, ""))
        chunks.append(dxf_pair(0, "ENDTAB"))
    chunks.append(dxf_pair(0, "ENDSEC"))

    chunks.append(dxf_pair(0, "SECTION"))
    chunks.append(dxf_pair(2, "ENTITIES"))
    for index, start in enumerate(points):
        end = points[(index + 1) % len(points)]
        chunks.append(dxf_pair(0, "LINE"))
        chunks.append(dxf_pair(8, "EP_BOUNDARY"))
        chunks.append(dxf_pair(62, 1))
        chunks.append(dxf_pair(10, f"{start[0]:.4f}"))
        chunks.append(dxf_pair(20, f"{start[1]:.4f}"))
        chunks.append(dxf_pair(30, "0.0"))
        chunks.append(dxf_pair(11, f"{end[0]:.4f}"))
        chunks.append(dxf_pair(21, f"{end[1]:.4f}"))
        chunks.append(dxf_pair(31, "0.0"))

    if include_text:
        chunks.append(dxf_pair(0, "TEXT"))
        chunks.append(dxf_pair(8, "EP_TEXT"))
        chunks.append(dxf_pair(10, f"{cx:.4f}"))
        chunks.append(dxf_pair(20, f"{cy:.4f}"))
        chunks.append(dxf_pair(30, "0.0"))
        chunks.append(dxf_pair(40, f"{text_height:.2f}"))
        chunks.append(dxf_pair(1, label))
        chunks.append(dxf_pair(50, "0.0"))
        chunks.append(dxf_pair(7, "STANDARD"))
        chunks.append(dxf_pair(72, 1))
        chunks.append(dxf_pair(11, f"{cx:.4f}"))
        chunks.append(dxf_pair(21, f"{cy:.4f}"))
        chunks.append(dxf_pair(31, "0.0"))
        chunks.append(dxf_pair(73, 2))

    chunks.append(dxf_pair(0, "ENDSEC"))
    chunks.append(dxf_pair(0, "EOF"))
    path.write_text("".join(chunks), encoding="ascii")


def parse_args():
    parser = argparse.ArgumentParser(description="Export one EGKN parcel boundary to DXF for manual Revit import.")
    parser.add_argument("cadnum", help="Cadastral number, e.g. 020361555159")
    parser.add_argument("--data", default="data", help="Folder with parcels_*.geojson and parcels_*.csv")
    parser.add_argument("--out", help="Output DXF path")
    parser.add_argument("--absolute", action="store_true", help="Keep source UTM coordinates instead of moving first point to 0,0")
    parser.add_argument("--with-text", action="store_true", help="Add a text label. Revit may reject text in some DXF imports.")
    parser.add_argument("--no-text", action="store_true", help="Deprecated: DXF is lines-only by default.")
    return parser.parse_args()


def main():
    args = parse_args()
    cadnum = normalize_cadnum(args.cadnum)
    data_dir = Path(args.data).resolve()
    code, row = find_code_by_csv(data_dir, cadnum)
    if not code:
        raise SystemExit(f"Parcel {cadnum} was not found in {data_dir}")

    geojson_path = data_dir / f"parcels_{code}.geojson"
    feature = find_feature(geojson_path, cadnum, row.get("gid") if row else None)
    if feature is None:
        raise SystemExit(f"Parcel {cadnum} was found in CSV but not in {geojson_path}")

    points = clean_points(exterior_ring(feature.get("geometry") or {}), relative=not args.absolute)
    props = feature.get("properties") or {}
    area = float(props.get("shape_area") or polygon_area(points))
    perimeter = polygon_perimeter(points)
    out_path = Path(args.out) if args.out else data_dir / f"parcel_{cadnum}.dxf"
    write_dxf(out_path.resolve(), points, cadnum, area, perimeter, include_text=args.with_text and not args.no_text)

    print(f"Saved DXF: {out_path.resolve()}")
    print(f"Points: {len(points)}")
    print(f"District: {props.get('district_code')} {props.get('district_name')}")
    print(f"Address: {props.get('address_ru')}")
    print(f"Area: {area:.2f} sq.m")
    print(f"Perimeter: {perimeter:.2f} m")


if __name__ == "__main__":
    main()
