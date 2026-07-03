#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

from export_parcel_dxf import polygon_area, polygon_perimeter, write_dxf


def parse_float(value):
    if value is None:
        return None
    text = str(value).strip().replace(" ", "").replace("\u00a0", "")
    if not text:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def detect_delimiter(sample):
    for delimiter in (";", "\t", ","):
        if delimiter in sample:
            return delimiter
    return ";"


def read_csv_points(path):
    text = None
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text = Path(path).read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError(f"Cannot read CSV: {path}")

    rows = list(csv.reader(text.splitlines(), delimiter=detect_delimiter(text[:2048])))
    rows = [row for row in rows if any(str(cell).strip() for cell in row)]
    if not rows:
        raise ValueError("CSV is empty")

    header = [cell.strip().lower() for cell in rows[0]]
    x_index = next((i for i, name in enumerate(header) if name in ("x", "xcoord", "x_coord", "east", "easting")), None)
    y_index = next((i for i, name in enumerate(header) if name in ("y", "ycoord", "y_coord", "north", "northing")), None)

    data_rows = rows[1:] if x_index is not None and y_index is not None else rows
    points = []
    for row in data_rows:
        if x_index is not None and y_index is not None and len(row) > max(x_index, y_index):
            x = parse_float(row[x_index])
            y = parse_float(row[y_index])
        else:
            numbers = [parse_float(cell) for cell in row]
            numbers = [number for number in numbers if number is not None]
            if len(numbers) < 2:
                continue
            x, y = numbers[-2], numbers[-1]
        if x is not None and y is not None:
            points.append((x, y))

    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < 3:
        raise ValueError("Need at least 3 coordinate points")
    return points


def normalize_points(points, relative=True):
    if not relative:
        return list(points)
    base_x, base_y = points[0]
    return [(x - base_x, y - base_y) for x, y in points]


def csv_to_dxf(csv_path, out_path=None, label=None, relative=True, include_text=False):
    csv_path = Path(csv_path).resolve()
    points = normalize_points(read_csv_points(csv_path), relative=relative)
    out_path = Path(out_path).resolve() if out_path else csv_path.with_suffix(".dxf")
    label = label or csv_path.stem
    area = polygon_area(points)
    perimeter = polygon_perimeter(points)
    write_dxf(out_path, points, label, area, perimeter, include_text=include_text)
    return {
        "out": str(out_path),
        "points": len(points),
        "area": area,
        "perimeter": perimeter,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Convert Point/X/Y CSV to DXF.")
    parser.add_argument("csv", help="Input CSV file")
    parser.add_argument("--out", help="Output DXF path")
    parser.add_argument("--label", help="DXF text label")
    parser.add_argument("--absolute", action="store_true", help="Keep source coordinates instead of moving first point to 0,0")
    parser.add_argument("--with-text", action="store_true", help="Add a text label. Revit may reject text in some DXF imports.")
    return parser.parse_args()


def main():
    args = parse_args()
    result = csv_to_dxf(args.csv, args.out, args.label, relative=not args.absolute, include_text=args.with_text)
    print(f"Saved DXF: {result['out']}")
    print(f"Points: {result['points']}")
    print(f"Area: {result['area']:.2f} sq.m")
    print(f"Perimeter: {result['perimeter']:.2f} m")


if __name__ == "__main__":
    main()
