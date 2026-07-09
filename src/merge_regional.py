"""Merge NUTS-assigned (or country-assigned) lending data with a regional indicator.

Aggregates project-level lending up to a region x year panel, then
left-joins it onto a regional indicator table (indexed by nuts_code and
year) so that every region-year in the indicator table appears in the
output - including region-years with no recorded lending activity. The
result is a clean, analysis-ready panel saved to outputs/merged_panel.csv.

Mode-aware, at two levels:
- Geography: sample mode's "region" is a genuine NUTS2 region (from the
  point-in-polygon spatial join in assign_nuts.assign_nuts_regions). Real
  mode's "region" is a country (from the country-level attribute join in
  assign_nuts.assign_country_region), since the real EIB export has no
  project-level coordinates - see assign_nuts.py.
- Indicator: sample mode uses a synthetic gross-fixed-capital-formation-
  style indicator; real mode uses Eurostat's nama_10r_2gdp (regional GDP),
  summed up from NUTS2 to country level to match the coarser real-mode
  geography. Both are standardized onto a common internal column,
  regional_indicator_eur_millions, plus a regional_indicator_name label
  saying what it actually measures.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from src import config
    from src.assign_nuts import assign_country_region, assign_nuts_regions, get_region_names, load_nuts_boundaries
    from src.load_lending import load_lending_data
except ImportError:
    import config
    from assign_nuts import assign_country_region, assign_nuts_regions, get_region_names, load_nuts_boundaries
    from load_lending import load_lending_data

DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "outputs" / "merged_panel.csv"

REGIONAL_VALUE_COLUMNS = {
    "sample": "gfcf_eur_millions",
    "real": "gdp_eur_millions",
}
REGIONAL_INDICATOR_LABELS = {
    "sample": "Gross fixed capital formation (synthetic)",
    "real": "Gross domestic product, current prices, MIO_EUR, summed to country level (Eurostat nama_10r_2gdp)",
}


def load_regional_indicators(mode: str | None = None) -> pd.DataFrame:
    """Load the regional indicator panel for the given (or auto-detected) mode.

    In real mode the source file is at NUTS2 granularity but real-mode
    lending can only be assigned to country level (see assign_nuts.py), so
    it's summed up to country level here (nuts_code truncated to its
    2-character country prefix) to match. Standardizes the mode-specific
    value column onto a common internal column,
    regional_indicator_eur_millions, and attaches regional_indicator_name
    describing what it actually measures.
    """
    resolved_mode = config.resolve_mode(mode)
    path = config.get_paths(resolved_mode).regional_path
    df = pd.read_csv(path)

    value_col = REGIONAL_VALUE_COLUMNS[resolved_mode]
    required = {"nuts_code", "year", value_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"regional indicator file at {path} is missing columns: {missing}")

    if resolved_mode == "real":
        df = df.copy()
        df["nuts_code"] = df["nuts_code"].str[:2]
        df = df.groupby(["nuts_code", "year"], as_index=False)[value_col].sum()

    df = df.rename(columns={value_col: "regional_indicator_eur_millions"})
    df["regional_indicator_name"] = REGIONAL_INDICATOR_LABELS[resolved_mode]
    return df[["nuts_code", "year", "regional_indicator_eur_millions", "regional_indicator_name"]]


def build_region_year_panel(lending_with_nuts: pd.DataFrame) -> pd.DataFrame:
    """Aggregate project-level lending (with region codes assigned) to region x year totals."""
    df = lending_with_nuts.copy()
    df["climate_signed_amount_eur"] = df["signed_amount_eur"].where(df["climate_action"], 0.0)

    grouped = df.groupby(["nuts2_code", "signed_year"], as_index=False).agg(
        num_projects=("project_id", "count"),
        total_signed_amount_eur=("signed_amount_eur", "sum"),
        climate_signed_amount_eur=("climate_signed_amount_eur", "sum"),
    )
    return grouped.rename(columns={"signed_year": "year"})


def merge_with_regional_indicator(
    lending_with_nuts: pd.DataFrame, regional_df: pd.DataFrame, region_names: pd.DataFrame
) -> pd.DataFrame:
    """Build the final region x year panel: lending aggregates + regional indicator.

    Starts from `regional_df` (the indicator panel skeleton) and left-joins
    the lending aggregates onto it, so region-years with no lending activity
    are kept with zero-valued lending columns rather than being dropped. If
    the regional indicator uses a different code vintage than `region_names`,
    some nuts_code values won't find a name match - this is reported (see
    main()), not silently patched with an invented crosswalk.
    """
    panel = build_region_year_panel(lending_with_nuts).rename(columns={"nuts2_code": "nuts_code"})

    merged = regional_df.merge(region_names, on="nuts_code", how="left")
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
        "regional_indicator_eur_millions",
        "regional_indicator_name",
    ]
    return merged[cols].sort_values(["nuts_code", "year"]).reset_index(drop=True)


def main() -> None:
    """Run the full lending -> region -> regional-indicator merge and save the panel."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "real"], default=None,
                         help="Data mode. Defaults to auto-detect (real if data/real/ is fully populated).")
    args = parser.parse_args()
    resolved_mode = config.resolve_mode(args.mode)

    lending = load_lending_data(mode=resolved_mode)
    nuts_gdf = load_nuts_boundaries(mode=resolved_mode)
    if resolved_mode == "sample":
        lending_with_nuts = assign_nuts_regions(lending, nuts_gdf)
    else:
        lending_with_nuts = assign_country_region(lending, nuts_gdf)
    region_names = get_region_names(resolved_mode, nuts_gdf)
    regional = load_regional_indicators(mode=resolved_mode)

    panel = merge_with_regional_indicator(lending_with_nuts, regional, region_names)

    DEFAULT_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(DEFAULT_OUTPUT_PATH, index=False)

    print(f"Mode: {resolved_mode}")
    print(f"Built region-year panel: {len(panel)} rows ({panel['nuts_code'].nunique()} regions x "
          f"{panel['year'].nunique()} years)")
    print(f"Saved to {DEFAULT_OUTPUT_PATH}")
    print()
    print(panel.head(10).to_string(index=False))
    print()
    print(f"Region-years with zero recorded lending: {(panel['num_projects'] == 0).sum()} / {len(panel)}")

    unmatched_names = panel["nuts_name"].isna().sum()
    if unmatched_names:
        n_codes = panel.loc[panel["nuts_name"].isna(), "nuts_code"].nunique()
        print(
            f"WARNING: {unmatched_names} panel rows ({n_codes} distinct nuts_code values) have no "
            "matching region name from the boundaries file - the regional indicator may use a "
            "different code vintage. Not auto-corrected; see README known limitations."
        )


if __name__ == "__main__":
    main()
