# Aktobe Parcel Tool

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![DXF](https://img.shields.io/badge/DXF-R12%20LINE-brightgreen)
![Revit](https://img.shields.io/badge/Revit-Import%20CAD-186BFF)
![Windows](https://img.shields.io/badge/Windows-GUI-0078D4?logo=windows&logoColor=white)

Удобная Windows-программа для ЭП/генплана: вводишь кадастровый номер или выбираешь CSV с координатами, а на выходе получаешь `CSV` и легкий `DXF R12 lines only`, который нормально импортируется в Revit.

Проект сделан под рабочий сценарий: быстро получить границы участка из публичной кадастровой карты ЕГКН, вставить контур в Revit и дальше спокойно делать генплан вручную.

## Что умеет

- `Кадастровый номер -> CSV + DXF`
- `Любой CSV с точками -> DXF`
- DXF пишется в старом формате `R12 LINE`, без текста и сложных сущностей
- первая точка участка переносится в `0,0`, чтобы контур не улетал далеко от проекта
- есть GUI без консоли: запуск через `Start_ParcelTool.vbs`
- есть скрипты для скачивания участков ЕГКН по районам Актюбинской области

## Быстрый старт

1. Установи Python 3 для Windows.
2. Скачай или клонируй этот репозиторий.
3. Дважды нажми:

```text
Start_ParcelTool.vbs
```

4. В этой сборке данные для Актюбинской области уже лежат в папке `data`.
5. Если уже есть свой CSV, открой вкладку `CSV -> DXF` и выбери файл.

## Формат CSV

Лучше всего подходит такой CSV:

```csv
Point;X;Y
1;0.0000;0.0000
2;12.3456;4.5678
3;10.0000;18.0000
```

Программа также понимает CSV с колонками `X/Y`, `xcoord/ycoord`, `east/north` или строки, где последние два числа являются координатами.

## Импорт в Revit

В Revit:

```text
Вставка -> Импорт CAD -> выбрать .dxf
Import units: Meter
Positioning: Auto - Origin to Origin
```

Если нужны именно линии Revit, после импорта можно выделить CAD-объект и сделать `Partial Explode`.

Подробная инструкция лежит в [docs/REVIT_IMPORT.md](docs/REVIT_IMPORT.md).

## Скачивание данных ЕГКН


Скачать эти районы:

```powershell
python .\scripts\fetch_egkn_parcels.py --codes 02036 02040 02034 --out .\data --page-size 5000
```

Проверить только количество объектов без скачивания:

```powershell
python .\scripts\fetch_egkn_parcels.py --codes 02036 02040 02034 --out .\data --dry-run
```

Выгрузить всю Актюбинскую область:

```powershell
python .\scripts\fetch_egkn_parcels.py --all-aktobe --out .\data_all_aktobe --page-size 5000
```

## Пример

В папке `examples` лежит тестовый участок:

- кадастровый номер: `02034036038`
- район: `02034`, Хромтауский район
- площадь: около `1086.64 м2`
- результат: `examples/parcel_02034036038.dxf`

Этот пример нужен, чтобы быстро проверить импорт в Revit без скачивания всей базы.

## Структура проекта

```text
.
├─ ParcelTool.pyw                 # главное окно программы
├─ Start_ParcelTool.vbs           # запуск без консоли
├─ scripts/
│  ├─ fetch_egkn_parcels.py       # скачать участки ЕГКН
│  ├─ extract_parcel_points.py    # кадастровый номер -> CSV
│  ├─ export_parcel_dxf.py        # кадастровый номер -> DXF
│  └─ csv_to_dxf.py               # любой CSV -> DXF
├─ data/                          # сюда кладутся большие локальные базы
├─ exports/                       # сюда программа сохраняет результат
├─ examples/                      # маленький проверочный пример
└─ docs/
   └─ REVIT_IMPORT.md
```

## Заметки

В этой полной сборке по Актобе файлы `parcels_*.geojson` и `parcels_*.csv` уже добавлены в `data`, чтобы программа работала сразу после распаковки или клонирования. Служебные поля ЕГКН по умолчанию не сохраняются, потому что для ЭП обычно нужны границы, кадастровый номер, адрес и площадь.

## Лицензия

MIT. Можно использовать и дорабатывать под свой рабочий процесс.
