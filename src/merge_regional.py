"""Merge NUTS-assigned lending data with a Eurostat-style regional indicator.

Aggregates project-level lending up to a NUTS2 x year panel, then left-joins
it onto a regional indicator table (indexed by nuts_code and year) so that
every region-year in the indicator table appears in the output - including
region-years with no recorded lending activity. The result is a clean,
analysis-ready panel saved to outputs/merged_panel.csv.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src.assign_nuts import assign_nuts_regions, load_nuts_boundaries
    from src.load_lending import load_lending_data
except ImportError:
    from assign_nuts import assign_nuts_regions, load_nuts_boundaries
    from load_lending import load_lending_data

DEFAULT_REGIONAL_PATH = Path(__file__).resolve().parent.parent / "data" / "sample" / "regional_indicators.csv"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "outputs" / "merged_panel.csv"


def load_regional_indicators(path: Path | str = DEFAULT_REGIONAL_PATH) -> pd.DataFrame:
    """Load the Eurostat-style regional indicator table (nuts_code, year, gfcf_eur_millions)."""
    df = pd.read_csv(path)
    required = {"nuts_code", "year", "gfcf_eur_millions"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"regional indicator file at {path} is missing columns: {missing}")
    return df


def build_region_year_panel(lending_with_nuts: pd.DataFrame) -> pd.DataFrame:
    """Aggregate project-level lending (with NUTS codes assigned) to NUTS2 x year totals."""
    df = lending_with_nuts.copy()
    df["climate_signed_amount_eur"] = df["signed_amount_eur"].where(df["climate_action"], 0.0)

    grouped = df.groupby(["nuts2_code", "signed_year"], as_index=False).agg(
        num_projects=("project_id", "count"),
        total_signed_amount_eur=("signed_amount_eur", "sum"),
        climate_signed_amount_eur=("climate_signed_amount_eur", "sum"),
    )
    return grouped.rename(columns={"signed_year": "year"})


def merge_with_regional_indicator(
    lending_with_nuts: pd.DataFrame, regional_df: pd.DataFrame, nuts_gdf
) -> pd.DataFrame:
    """Build the final NUTS2 x year panel: lending aggregates + regional indicator.

    Starts from `regional_df` (the indicator panel skeleton) and left-joins
    the lending aggregates onto it, so region-years with no lending activity
    are kept with zero-valued lending columns rather than being dropped.
    """
    nuts2_names = (
        nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == 2, ["NUTS_ID", "NUTS_NAME"]]
        .rename(columns={"NUTS_ID": "nuts_code", "NUTS_NAME": "nuts_name"})
    )

    panel = build_region_year_panel(lending_with_nuts).rename(columns={"nuts2_code": "nuts_code"})

    merged = regional_df.merge(nuts2_names, on="nuts_code", how="left")
    merged = merged.merge(panel, on=["nuts_code", "year"], how="left")

    fill_cols = ["num_projects", "total_signed_amount_eur", "climate_signed_amount_eur"]
    merged[fill_cols] = merged[fill_cols].fillna(0)
    merged["num_projects"] = merged["num_projects"].astype(int)

    merged["climate_action_share"] = np.where(
        merged["total_signed_amount_eur"] > 0,
        merged["climate_signed_amount_eur"] / merged["total_signed_amount_eur"],
        np.nan,
    )

    cols = [
        "nuts_code",
        "nuts_name",
        "year",
        "num_projects",
        "total_signed_amount_eur",
        "climate_signed_amount_eur",
        "climate_action_share",
        "gfcf_eur_millions",
    ]
    return merged[cols].sort_values(["nuts_code", "year"]).reset_index(drop=True)


def main() -> None:
    """Run the full lending -> NUTS -> regional-indicator merge and save the panel."""
    lending = load_lending_data()
    nuts_gdf = load_nuts_boundaries()
    lending_with_nuts = assign_nuts_regions(lending, nuts_gdf)
    regional = load_regional_indicators()

    panel = merge_with_regional_indicator(lending_with_nuts, regional, nuts_gdf)

    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(DEFAULT_OUTPUT_PATH, index=False)

    print(f"Built region-year panel: {len(panel)} rows ({panel['nuts_code'].nunique()} regions x "
          f"{panel['year'].nunique()} years)")
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")
    print()
    print(panel.head(10).to_string(index=False))
    print()
    print(f"Region-years with zero recorded lending: {(panel['num_projects'] == 0).sum()} / {len(panel)}")


if __name__ == "__main__":
    main()
