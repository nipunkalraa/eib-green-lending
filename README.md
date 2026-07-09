# EIB Green-Lending Regional Pipeline

A small, reproducible Python pipeline that reproduces a regional green-finance data workflow:
it takes European Investment Bank (EIB) green-lending project data, extracts key figures from
project appraisal PDFs, assigns each investment a NUTS2/NUTS3 region via a spatial join,
merges it with a Eurostat-style regional indicator, and produces a choropleth map plus a
saved, analysis-ready regional panel dataset. It was built as a portfolio demonstrator of
data-construction and geospatial-linkage skills relevant to green public finance and regional
economic development research.

> **This repository currently runs on generated synthetic sample data with the correct
> schema.** No real EIB, GISCO or Eurostat data has been downloaded. Real data can be dropped
> into `data/real/` and the pipeline pointed at it - see [Phase 2](#phase-2--real-data) below.
> No statistical "findings" are claimed anywhere in this repository; every figure produced by
> the pipeline is either synthetic or a plain descriptive aggregate of that synthetic data.

![Green lending intensity choropleth (synthetic sample data)](outputs/choropleth_preview.png)

## What this demonstrates

- **Dataset construction from heterogeneous sources** - combining a project-level CSV with
  figures extracted from PDF documents into a single analysis-ready table.
- **PDF extraction** - systematic, regex-based extraction of labelled financial variables
  (total project cost, EIB finance, co-financing) from project appraisal PDFs using
  `pdfplumber`.
- **Spatial joins for geographic identifiers** - point-in-polygon joins with `geopandas` to
  assign each investment a consistent NUTS2 and NUTS3 region code, with explicit CRS handling
  (EPSG:4326).
- **Merging on regional keys** - aggregating project-level data to a region-by-year panel and
  joining it onto a regional economic indicator by NUTS code and year.
- **Visualisation** - a choropleth of regional lending intensity, plus sector and time-series
  breakdowns.

## Data sources (Phase 2 targets)

The pipeline is designed around three public data sources. None are downloaded yet - this is
where Phase 2 will point the pipeline once the sample-data version is working end-to-end.

| Source | What it provides | URL |
|---|---|---|
| EIB Open Data / list of financed projects | Project-level records: amounts, sectors, locations, signature dates | https://data.eib.org/ |
| Eurostat GISCO - NUTS boundaries | Official NUTS2/NUTS3 boundary geometries for the spatial join | https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics |
| Eurostat regional accounts | Regional economic indicators (e.g. gross fixed capital formation at NUTS2, employment/firm demography at NUTS3) | https://ec.europa.eu/eurostat/web/regions/database |

## How to run

Requires Python 3.11+ and no Conda (plain `venv` + `pip`).

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

**Option A - run the notebook** (recommended; this is what a reader is most likely to open):

```bash
jupyter notebook notebook.ipynb
```

Run all cells top to bottom. The first cell regenerates the synthetic sample data with a
fixed seed, so re-running the whole notebook always reproduces the same output.

**Option B - run the pipeline stage by stage** from the command line:

```bash
python src/generate_synthetic.py   # writes data/sample/*
python src/load_lending.py         # loads + validates the lending CSV
python src/extract_pdf.py          # extracts figures from the sample PDFs
python src/assign_nuts.py          # spatial join -> NUTS2/NUTS3 codes
python src/merge_regional.py       # builds outputs/merged_panel.csv
python src/visualise.py            # writes outputs/*.png
```

## Methodology

**Data construction (`generate_synthetic.py`, `load_lending.py`).** The sample lending table
(`data/sample/lending.csv`) is generated with a fixed random seed: 200 projects across 10
European countries, several sectors (a mix of green sectors - renewable energy, energy
efficiency, clean transport, water management - and non-green sectors), and signed years
2014-2023. `load_lending.py` validates the schema (required columns, coordinate ranges,
positive amounts, no duplicate project IDs) before anything downstream touches it.

**PDF extraction (`extract_pdf.py`).** Five synthetic EIB-style project appraisal PDFs are
generated with `reportlab`, each containing narrative text plus three labelled EUR figures.
`extract_pdf.py` uses `pdfplumber` to pull the text back out and regexes out
`total_project_cost_eur`, `eib_finance_eur` and `cofinancing_eur`, then sanity-checks that EIB
finance plus co-financing reconstructs the total cost. This demonstrates the extraction
machinery on a small corpus; it is a regex-based parser tuned to this document's label format,
not a general-purpose PDF parser.

**Spatial join (`assign_nuts.py`).** Each project's `(lat, lon)` is converted to a point and
joined against a NUTS boundaries file with `geopandas.sjoin`. The synthetic boundaries file
(`data/sample/nuts_boundaries.geojson`) contains simple rectangular polygons standing in for
real GISCO geometries, but mirrors their structure: both NUTS2 and NUTS3 features live in one
file, distinguished by `LEVL_CODE`, and NUTS3 codes nest under their parent NUTS2 code (e.g.
`DE101` under `DE10`) the same way real NUTS codes do. Both the points and the polygons are
explicit EPSG:4326 before the join.

**Regional merge (`merge_regional.py`).** Project-level lending is aggregated to a NUTS2 x
year panel (total signed amount, climate-relevant amount, project counts), then left-joined
onto a synthetic Eurostat-style regional indicator (`gfcf_eur_millions`, standing in for gross
fixed capital formation - the indicator named in Eurostat's regional accounts for NUTS2). The
join starts from the indicator table so every region-year is retained, including ones with no
recorded lending activity, rather than silently dropping them.

**Visualisation (`visualise.py`).** Three plots, all `matplotlib`/`geopandas`: a choropleth of
total climate-relevant lending per NUTS2 region over 2014-2023, a bar chart of total lending
by sector, and a line chart of lending over time (all sectors vs. climate-relevant only).

## Repository structure

```
eib-green-lending/
├── src/
│   ├── generate_synthetic.py   # seeded synthetic data generator (lending, NUTS, regional, PDFs)
│   ├── load_lending.py         # load + validate the lending CSV
│   ├── extract_pdf.py          # pdfplumber extraction from project PDFs
│   ├── assign_nuts.py          # point-in-polygon join -> NUTS2/NUTS3 codes
│   ├── merge_regional.py       # region-by-year panel + regional indicator merge
│   └── visualise.py            # choropleth, sector, and time-series charts
├── data/
│   ├── sample/                 # synthetic sample data (generated, not hand-written)
│   └── real/                   # empty - Phase 2 real data goes here
├── outputs/                    # generated PNGs + merged_panel.csv (gitignored except the README preview image)
├── notebook.ipynb              # narrative walkthrough of the full pipeline
├── requirements.txt
└── README.md
```

## Limitations

- All data in this repository is synthetic: fake rectangular "regions" instead of real NUTS
  geometries, and randomly generated financial figures. Nothing here is a real economic
  estimate.
- The sample is small by design (200 projects, 5 PDFs) - enough to exercise every stage of the
  pipeline, not to represent the scale of a real 20-year EIB panel.
- The PDF extraction is a regex parser tuned to the label format used in the synthetic
  documents. Real EIB project appraisal PDFs would need their own extraction rules (and likely
  more defensive handling of missing/malformed fields).
- No causal inference or econometric modelling (e.g. difference-in-differences, event-study)
  is included. This repository's scope is data construction and descriptive visualisation.
- The synthetic NUTS regions don't overlap by construction, so the spatial join here can't
  demonstrate how the pipeline would behave with genuinely adjacent or oddly-shaped real
  boundaries.

## Phase 2 - real data

To swap in real data: download EIB project records, GISCO NUTS boundary files, and Eurostat
regional accounts data into `data/real/`, then point `load_lending.py`, `assign_nuts.py`, and
`merge_regional.py` at those files instead of the `data/sample/` defaults. Each module's
`load_*` function takes a `path` argument for exactly this purpose - the transformation logic
downstream doesn't need to change, as long as the real files expose the same columns.

## License

MIT - see [LICENSE](LICENSE).
