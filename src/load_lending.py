"""Load and validate an EIB-style green-lending project CSV.

Mode-aware: in "sample" mode this reads the synthetic sample at
data/sample/lending.csv. In "real" mode it reads a real, manually-exported
EIB financed-projects file from data/real/eib/eib_projects.csv (despite the
.csv extension, EIB's "Export to Excel" produces a genuine .xlsx file - see
_load_real_raw), mapping its columns onto the same internal schema the rest
of the pipeline expects. See src/config.py for path resolution and mode
auto-detection.

The real export (eib.org/en/projects/loans/index.htm) has columns: Name,
Region, Country or Territory, Sector, Signature Date, Signed Amount,
Description. It has no project ID, no city, and critically no coordinates -
real mode therefore does country-level regional matching instead of a
point-in-polygon spatial join (see assign_nuts.assign_country_region).
climate_action is derived via keyword matching on Sector/Description, since
the export exposes no official EIB climate-classification field - see
_derive_climate_action.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

try:
    from src import config
except ImportError:
    import config

REQUIRED_COLUMNS = [
    "project_id",
    "project_name",
    "country",
    "city",
    "lat",
    "lon",
    "signed_amount_eur",
    "sector",
    "climate_action",
    "signed_year",
]

# Keyword proxy for climate relevance, applied to the real export's Sector +
# Description text. Not an official EIB classification - the public search
# export doesn't expose EIB's internal Climate Action flag, so this is an
# honest best-effort substitute, documented as such wherever it's used.
CLIMATE_KEYWORDS = [
    "climate", "renewable", "green", "decarbon", "low carbon", "low-carbon",
    "solar", "wind farm", "wind power", "hydropower", "clean energy",
    "energy efficiency", "environmental sustainability", "emission reduction",
    "sustainable transport", "electric vehicle", "e-mobility",
]


def _derive_climate_action(sector: pd.Series, description: pd.Series) -> pd.Series:
    """Heuristically flag climate-relevant rows via keyword matching (real mode only)."""
    text = (sector.fillna("") + " " + description.fillna("")).str.lower()
    pattern = "|".join(re.escape(k) for k in CLIMATE_KEYWORDS)
    return text.str.contains(pattern, regex=True)


def _parse_signed_amount(raw: pd.Series) -> pd.Series:
    """Strip currency symbol/commas from the real export's 'Signed Amount' column."""
    cleaned = raw.astype(str).str.replace(r"[^\d.]", "", regex=True)
    return pd.to_numeric(cleaned, errors="coerce")


def _map_real_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map the real EIB financed-projects export onto the internal schema.

    project_id is synthesized from row position (the export has none). city
    is left blank and lat/lon are left as NaN (the export has none of these
    either - real mode's geography stops at country level). Rows missing an
    essential field (name, amount, year, country) are dropped, with a
    printed count, rather than silently coerced.
    """
    out = pd.DataFrame(index=df.index)
    out["project_id"] = [f"EIB-REAL-{i:06d}" for i in range(len(df))]
    out["project_name"] = df["Name"]
    out["country"] = df["Country or Territory"]
    out["city"] = ""
    out["lat"] = float("nan")
    out["lon"] = float("nan")
    out["signed_amount_eur"] = _parse_signed_amount(df["Signed Amount"])
    out["sector"] = df["Sector"]
    out["climate_action"] = _derive_climate_action(df["Sector"], df["Description"])
    out["signed_year"] = pd.to_datetime(df["Signature Date"], dayfirst=True, errors="coerce").dt.year

    n_before = len(out)
    out = out.dropna(subset=["project_name", "signed_amount_eur", "signed_year", "country"]).copy()
    out = out[out["signed_amount_eur"] > 0].copy()
    n_dropped = n_before - len(out)
    if n_dropped:
        print(f"Dropping {n_dropped} real EIB row(s) with missing or non-positive project_name/amount/year/country")

    out["signed_year"] = out["signed_year"].astype(int)
    return out.reset_index(drop=True)


def _load_real_raw(path: Path) -> pd.DataFrame:
    """Load the real EIB export. Despite the .csv extension it's a genuine .xlsx file."""
    return pd.read_excel(path, engine="openpyxl")


def load_lending_data(mode: str | None = None, path: Path | str | None = None) -> pd.DataFrame:
    """Load, validate and type-cast an EIB-style lending project table.

    Resolves the input path via config.get_paths(mode) unless `path` is
    given explicitly. In real mode, the raw EIB export's columns are mapped
    onto the internal schema first (see _map_real_columns); the same
    validation then applies to both modes. Raises ValueError if the schema
    doesn't match or any row fails validation.
    """
    resolved_mode = config.resolve_mode(mode)
    resolved_path = Path(path) if path is not None else config.get_paths(resolved_mode).lending_path

    if resolved_mode == "real":
        df = _load_real_raw(resolved_path)
        df = _map_real_columns(df)
    else:
        df = pd.read_csv(resolved_path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"lending data at {resolved_path} is missing required columns: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["project_id"] = df["project_id"].astype(str)
    df["project_name"] = df["project_name"].astype(str)
    df["country"] = df["country"].astype(str)
    df["city"] = df["city"].astype(str)
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    df["signed_amount_eur"] = df["signed_amount_eur"].astype(float)
    df["sector"] = df["sector"].astype(str)
    df["climate_action"] = df["climate_action"].astype(bool)
    df["signed_year"] = df["signed_year"].astype(int)

    if df["project_id"].duplicated().any():
        dupes = df.loc[df["project_id"].duplicated(), "project_id"].tolist()
        raise ValueError(f"duplicate project_id values found: {dupes}")
    # Missing coordinates are tolerated here (real EIB exports sometimes lack
    # lat/lon for a project) - they're dropped explicitly, with a printed
    # count, at the spatial-join stage rather than rejected at load time.
    if not df["lat"].dropna().between(-90, 90).all():
        raise ValueError("lat values outside the valid range [-90, 90]")
    if not df["lon"].dropna().between(-180, 180).all():
        raise ValueError("lon values outside the valid range [-180, 180]")
    if not (df["signed_amount_eur"] > 0).all():
        raise ValueError("signed_amount_eur must be positive for every row")
    # 1958 (not 1990): the real EIB export goes all the way back to the
    # Bank's first loans in 1959 - this is genuine history, not bad data.
    if not df["signed_year"].between(1958, 2035).all():
        raise ValueError("signed_year values outside the plausible range [1958, 2035]")

    return df.reset_index(drop=True)


def filter_climate_action(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows flagged as climate-relevant (climate_action is True)."""
    return df[df["climate_action"]].reset_index(drop=True)


def main() -> None:
    """Load the lending data for the given (or auto-detected) mode and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "real"], default=None,
                         help="Data mode. Defaults to auto-detect (real if data/real/ is fully populated).")
    args = parser.parse_args()

    resolved_mode = config.resolve_mode(args.mode)
    resolved_path = config.get_paths(resolved_mode).lending_path

    df = load_lending_data(mode=resolved_mode)
    print(f"Mode: {resolved_mode}")
    print(f"Loaded {len(df)} projects from {resolved_path}")
    print(df.dtypes)
    print()
    climate = filter_climate_action(df)
    print(f"Climate-relevant projects: {len(climate)} / {len(df)}")
    print(f"Total signed amount (all projects): EUR {df['signed_amount_eur'].sum():,.0f}")
    print(f"Total signed amount (climate-relevant only): EUR {climate['signed_amount_eur'].sum():,.0f}")
    print()
    print(df.head())


if __name__ == "__main__":
    main()
