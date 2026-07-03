# Папка data

Сюда кладутся локальные данные ЕГКН:

```text
parcels_02034.geojson
parcels_02034.csv
parcels_02036.geojson
parcels_02036.csv
parcels_02040.geojson
parcels_02040.csv
```

Эти файлы не хранятся в GitHub, потому что они большие и могут часто обновляться. Их можно скачать командой:

```powershell
python .\scripts\fetch_egkn_parcels.py --codes 02036 02040 02034 --out .\data --page-size 5000
```

После этого окно `ParcelTool.pyw` сможет искать участок по кадастровому номеру.
