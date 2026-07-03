#!/usr/bin/env python3
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
DEFAULT_EXPORTS = ROOT / "exports"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from csv_to_dxf import csv_to_dxf
from export_parcel_dxf import clean_points, polygon_perimeter, write_dxf
from extract_parcel_points import exterior_ring, find_code_by_csv, find_feature, normalize_cadnum, write_points_csv


class ParcelTool(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Кадастр -> CSV / DXF")
        self.geometry("720x430")
        self.minsize(680, 400)

        self.data_dir = tk.StringVar(value=str(ROOT / "data"))
        self.out_dir = tk.StringVar(value=str(DEFAULT_EXPORTS))
        self.cadnum = tk.StringVar()
        self.csv_path = tk.StringVar()
        self.csv_out_dir = tk.StringVar(value=str(DEFAULT_EXPORTS))
        self.csv_relative = tk.BooleanVar(value=True)

        self._build()

    def _build(self):
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)

        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)

        cad_tab = ttk.Frame(notebook, padding=12)
        csv_tab = ttk.Frame(notebook, padding=12)
        notebook.add(cad_tab, text="Кадастровый номер")
        notebook.add(csv_tab, text="CSV -> DXF")

        self._build_cad_tab(cad_tab)
        self._build_csv_tab(csv_tab)

        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=(10, 0))
        ttk.Button(bottom, text="Открыть папку exports", command=self.open_exports).pack(side="right")

    def _build_cad_tab(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Кадастровый номер").grid(row=0, column=0, sticky="w", pady=6)
        entry = ttk.Entry(parent, textvariable=self.cadnum, font=("Segoe UI", 12))
        entry.grid(row=0, column=1, sticky="ew", pady=6)
        entry.focus_set()

        ttk.Label(parent, text="Папка data").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.data_dir).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="Выбрать", command=self.pick_data_dir).grid(row=1, column=2, padx=(8, 0), pady=6)

        ttk.Label(parent, text="Куда сохранить").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.out_dir).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="Выбрать", command=self.pick_out_dir).grid(row=2, column=2, padx=(8, 0), pady=6)

        hint = (
            "Создает отдельную папку с кадастровым номером и кладет туда CSV с исходными координатами, CSV от 0,0 и рабочий DXF R12 lines only. "
            "DXF можно импортировать в Revit через Вставка -> Импорт CAD, единицы Meter."
        )
        ttk.Label(parent, text=hint, wraplength=620, foreground="#444").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(12, 6)
        )

        ttk.Button(parent, text="Создать CSV + DXF", command=self.make_from_cadnum).grid(
            row=4, column=1, sticky="e", pady=(18, 0)
        )

    def _build_csv_tab(self, parent):
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="CSV файл").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.csv_path).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="Выбрать", command=self.pick_csv).grid(row=0, column=2, padx=(8, 0), pady=6)

        ttk.Label(parent, text="Куда сохранить").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.csv_out_dir).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Button(parent, text="Выбрать", command=self.pick_csv_out_dir).grid(row=1, column=2, padx=(8, 0), pady=6)

        ttk.Checkbutton(
            parent,
            text="Перенести первую точку в 0,0",
            variable=self.csv_relative,
        ).grid(row=2, column=1, sticky="w", pady=8)

        hint = "Поддерживает CSV с колонками Point;X;Y, X/Y или строки, где последние два числа это X и Y."
        ttk.Label(parent, text=hint, wraplength=620, foreground="#444").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(12, 6)
        )

        ttk.Button(parent, text="Сделать DXF", command=self.make_from_csv).grid(
            row=4, column=1, sticky="e", pady=(18, 0)
        )

    def pick_data_dir(self):
        self._pick_dir(self.data_dir)

    def pick_out_dir(self):
        self._pick_dir(self.out_dir)

    def pick_csv_out_dir(self):
        self._pick_dir(self.csv_out_dir)

    def pick_csv(self):
        path = filedialog.askopenfilename(
            title="Выбери CSV",
            filetypes=[("CSV/TXT", "*.csv *.txt"), ("All files", "*.*")],
        )
        if path:
            self.csv_path.set(path)
            if not self.csv_out_dir.get():
                self.csv_out_dir.set(str(Path(path).parent))

    def _pick_dir(self, variable):
        path = filedialog.askdirectory(title="Выбери папку")
        if path:
            variable.set(path)

    def open_exports(self):
        path = Path(self.out_dir.get() or self.csv_out_dir.get() or ROOT / "exports")
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    def make_from_cadnum(self):
        try:
            cadnum = normalize_cadnum(self.cadnum.get())
            if not cadnum:
                raise ValueError("Введите кадастровый номер")

            data_dir = Path(self.data_dir.get()).resolve()
            out_root = Path(self.out_dir.get()).resolve()
            out_dir = out_root / cadnum
            out_dir.mkdir(parents=True, exist_ok=True)

            code, row = find_code_by_csv(data_dir, cadnum)
            if not code:
                raise ValueError(f"Участок {cadnum} не найден в {data_dir}")

            geojson_path = data_dir / f"parcels_{code}.geojson"
            feature = find_feature(geojson_path, cadnum, row.get("gid") if row else None)
            if feature is None:
                raise ValueError(f"Участок найден в CSV, но не найден в {geojson_path}")

            ring = exterior_ring(feature.get("geometry") or {})
            absolute_csv = out_dir / f"parcel_{cadnum}_points.csv"
            relative_csv = out_dir / f"parcel_{cadnum}_points_relative.csv"
            dxf_path = out_dir / f"parcel_{cadnum}.dxf"

            point_count = write_points_csv(absolute_csv, ring, relative=False)
            write_points_csv(relative_csv, ring, relative=True)

            props = feature.get("properties") or {}
            points = clean_points(ring, relative=True)
            area = float(props.get("shape_area") or 0) or 0.0
            perimeter = polygon_perimeter(points)
            write_dxf(dxf_path, points, cadnum, area, perimeter, include_text=False)

            self._write_info(out_dir / f"parcel_{cadnum}_info.txt", props, point_count, area, perimeter)
            messagebox.showinfo(
                "Готово",
                "Созданы файлы:\n"
                f"{absolute_csv.name}\n"
                f"{relative_csv.name}\n"
                f"{dxf_path.name}  (R12 lines only)\n\n"
                f"Точек: {point_count}\n"
                f"Площадь: {area:.2f} м2\n"
                f"Периметр: {perimeter:.2f} м",
            )
            os.startfile(out_dir)
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    def make_from_csv(self):
        try:
            csv_path = Path(self.csv_path.get()).resolve()
            if not csv_path.exists():
                raise ValueError("Выберите существующий CSV файл")

            out_dir = Path(self.csv_out_dir.get()).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            dxf_path = out_dir / f"{csv_path.stem}.dxf"
            result = csv_to_dxf(csv_path, dxf_path, label=csv_path.stem, relative=self.csv_relative.get(), include_text=False)
            messagebox.showinfo(
                "Готово",
                f"Создан DXF:\n{result['out']}\n\n"
                f"Точек: {result['points']}\n"
                f"Площадь: {result['area']:.2f} м2\n"
                f"Периметр: {result['perimeter']:.2f} м",
            )
            os.startfile(out_dir)
        except Exception as exc:
            messagebox.showerror("Ошибка", str(exc))

    @staticmethod
    def _write_info(path, props, point_count, area, perimeter):
        lines = [
            f"kad_nomer: {props.get('kad_nomer')}",
            f"district: {props.get('district_code')} {props.get('district_name')}",
            f"address_ru: {props.get('address_ru')}",
            f"points: {point_count}",
            f"area_m2: {area:.2f}",
            f"perimeter_m: {perimeter:.2f}",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    app = ParcelTool()
    app.mainloop()
