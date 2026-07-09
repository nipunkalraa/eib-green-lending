"""Download the real data sources into data/real/.

Fetches:
- GISCO NUTS2021 boundaries (GeoJSON, via the Nuts2json distribution) into data/real/gisco/
- Eurostat regional GDP (nama_10r_2gdp, via the `eurostat` package) into data/real/eurostat/
- A handful of real EIB project appraisal PDFs into data/real/eib/pdfs/

Does NOT fetch the EIB financed-projects CSV: EIB's "Finance Contracts
Multi-Criteria List" (eib.org/en/projects/loans/index.htm) is a JS-driven
search UI with an "Export to Excel" button and no static download URL, so
that file must be exported manually and placed at
data/real/eib/eib_projects.csv. This script checks for it and prints
instructions if it's missing.

Idempotent: skips any file that already exists unless --force is passed.
Each step is independent - a failure in one does not stop the others, and
every failure prints the URL plus a clear manual next step.
"""

from __future__ import annotations

import argparse

import pandas as pd
import requests

try:
    from src import config
except ImportError:
    import config

GISCO_URLS = {
    2: "https://raw.githubusercontent.com/eurostat/Nuts2json/master/pub/v2/2021/4326/20M/nutsrg_2.json",
    3: "https://raw.githubusercontent.com/eurostat/Nuts2json/master/pub/v2/2021/4326/20M/nutsrg_3.json",
}
GISCO_FALLBACK = "https://gisco-services.ec.europa.eu/distribution/v2/nuts/download/"

# Verified 2026-07-09: real, working EIB "Environmental and Social Data
# Sheet" PDFs pulled from the public register. Most do NOT contain a
# financial breakdown (EIB doesn't publish per-project EIB-finance /
# co-financing splits in this document type) - see extract_pdf.py and the
# README's known limitations for how this is handled honestly.
EIB_PDF_URLS = [
    "https://www.eib.org/attachments/registers/222930995.pdf",  # ENPAL REPOWEREU RENEWABLE ENERGY (Germany)
    "https://www.eib.org/attachments/registers/169004943.pdf",  # AGRIA FOOD PRODUCTION CAPACITY (Bulgaria)
    "https://www.eib.org/attachments/registers/246665048.pdf",  # NORDLB RENEWABLE ENERGY 2 (Germany/Regional EU)
    "https://www.eib.org/attachments/registers/213872807.pdf",  # SOLOMON SOLAR PV (Italy)
    "https://www.eib.org/attachments/registers/142353117.pdf",  # EDUCATION MONTPELLIER (France)
]

EIB_LOANS_SEARCH_URL = "https://www.eib.org/en/projects/loans/index.htm"


def _download(url: str, dest, force: bool) -> bool:
    """Download `url` to `dest` (a Path). Returns True on success."""
    if dest.exists() and not force:
        print(f"[skip] {dest} already exists (use --force to re-download)")
        return True
    print(f"Downloading {url}")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(resp.content)
        print(f"  saved to {dest}")
        return True
    except requests.RequestException as exc:
        print(f"  FAILED: {exc}")
        print(f"  Next step: open {url} in a browser and save it manually to {dest}")
        return False


def fetch_nuts_boundaries(force: bool = False) -> None:
    """Download NUTS2 and NUTS3 2021 boundary GeoJSON from Nuts2json."""
    dest_dir = config.REAL_DIR / "gisco"
    for level, url in GISCO_URLS.items():
        dest = dest_dir / f"nuts{level}_2021.geojson"
        ok = _download(url, dest, force)
        if not ok:
            print(f"  Fallback source: {GISCO_FALLBACK}")


def fetch_regional_indicator(force: bool = False) -> None:
    """Fetch Eurostat regional GDP (nama_10r_2gdp) via the eurostat package.

    Filters to unit == MIO_EUR and NUTS2-length (4-character) geo codes,
    melts from wide (one column per year) to long format, and saves
    (nuts_code, year, gdp_eur_millions) to data/real/eurostat/nama_10r_2gdp.csv.
    """
    dest = config.REAL_DIR / "eurostat" / "nama_10r_2gdp.csv"
    if dest.exists() and not force:
        print(f"[skip] {dest} already exists (use --force to re-download)")
        return

    print("Fetching nama_10r_2gdp via the eurostat package (dataset code: nama_10r_2gdp)")
    try:
        import eurostat

        raw = eurostat.get_data_df("nama_10r_2gdp")
        geo_col = raw.columns[2]
        raw = raw.rename(columns={geo_col: "geo"})
        raw = raw[raw["unit"] == "MIO_EUR"]
        raw = raw[raw["geo"].str.len() == 4]

        year_cols = [c for c in raw.columns if str(c).isdigit()]
        long_df = raw.melt(id_vars=["geo"], value_vars=year_cols, var_name="year", value_name="gdp_eur_millions")
        long_df = long_df.dropna(subset=["gdp_eur_millions"])
        long_df["year"] = long_df["year"].astype(int)
        long_df = long_df.rename(columns={"geo": "nuts_code"})
        long_df = long_df[["nuts_code", "year", "gdp_eur_millions"]].sort_values(["nuts_code", "year"])

        dest.parent.mkdir(parents=True, exist_ok=True)
        long_df.to_csv(dest, index=False)
        print(f"  saved {len(long_df)} rows to {dest}")
    except Exception as exc:  # noqa: BLE001 - report and fall back, don't crash the whole run
        print(f"  FAILED: {exc}")
        print("  Next step: try the fallback indicator nama_10r_3gva (NUTS3 gross value added), or")
        print("  download manually from https://ec.europa.eu/eurostat/databrowser/product/view/nama_10r_2gdp")


def fetch_eib_pdfs(force: bool = False) -> None:
    """Download the verified sample of real EIB project appraisal PDFs."""
    dest_dir = config.REAL_DIR / "eib" / "pdfs"
    for url in EIB_PDF_URLS:
        filename = url.rsplit("/", 1)[-1]
        dest = dest_dir / filename
        _download(url, dest, force)


def check_eib_csv() -> None:
    """Check for the manually-exported EIB financed-projects CSV; print instructions if missing."""
    dest = config.REAL_DIR / "eib" / "eib_projects.csv"
    if dest.exists():
        print(f"[found] {dest}")
        return
    print(f"[missing] {dest}")
    print("  EIB's financed-projects list has no static download URL (JS-driven export).")
    print(f"  Next step: open {EIB_LOANS_SEARCH_URL} in a browser, search/filter as needed,")
    print(f"  use \"Export to Excel\", and save the result as {dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download files even if they already exist.")
    args = parser.parse_args()

    print("=== NUTS boundaries (GISCO / Nuts2json) ===")
    fetch_nuts_boundaries(force=args.force)
    print()

    print("=== Regional indicator (Eurostat nama_10r_2gdp) ===")
    fetch_regional_indicator(force=args.force)
    print()

    print("=== EIB project appraisal PDFs ===")
    fetch_eib_pdfs(force=args.force)
    print()

    print("=== EIB financed-projects CSV ===")
    check_eib_csv()
    print()

    print(f"Real data status: real_data_available() = {config.real_data_available()}")


if __name__ == "__main__":
    main()
