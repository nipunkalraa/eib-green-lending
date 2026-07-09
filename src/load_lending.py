"""Load and validate an EIB-style green-lending project CSV.

In Phase 1 this reads the synthetic sample at data/sample/lending.csv. In
Phase 2 the same function can be pointed at a real, downloaded EIB project
list under data/real/, as long as it exposes the same columns.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample" / "lending.csv"

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


def load_lending_data(path: Path | str = DEFAULT_PATH) -> pd.DataFrame:
    """Load, validate and type-cast an EIB-style lending project table.

    Checks that every column in REQUIRED_COLUMNS is present, casts each
    column to a sensible dtype, and validates that coordinates and amounts
    fall within plausible ranges. Raises ValueError if the schema doesn't
    match or if any row fails validation.
    """
    path = Path(path)
    df = pd.read_csv(path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"lending data at {path} is missing required columns: {missing}")

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
    if not df["lat"].between(-90, 90).all():
        raise ValueError("lat values outside the valid range [-90, 90]")
    if not df["lon"].between(-180, 180).all():
        raise ValueError("lon values outside the valid range [-180, 180]")
    if not (df["signed_amount_eur"] > 0).all():
        raise ValueError("signed_amount_eur must be positive for every row")
    if not df["signed_year"].between(1990, 2035).all():
        raise ValueError("signed_year values outside the plausible range [1990, 2035]")

    return df.reset_index(drop=True)


def filter_climate_action(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows flagged as climate-relevant (climate_action is True)."""
    return df[df["climate_action"]].reset_index(drop=True)


def main() -> None:
    """Load the default (sample) lending data and print a summary."""
    df = load_lending_data()
    print(f"Loaded {len(df)} projects from {DEFAULT_PATH}")
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
