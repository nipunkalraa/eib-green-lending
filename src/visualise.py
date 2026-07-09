"""Produce the pipeline's three visualisations from the lending and panel data.

Generates:
- outputs/choropleth.png       total climate-relevant lending intensity per region
- outputs/by_sector.png        total lending by sector (all sectors, not just climate-relevant)
- outputs/over_time.png        total lending over time, all sectors vs. climate-relevant only

Also saves a smaller preview copy of the choropleth to
outputs/choropleth_preview.png, which is the one exception to outputs/ being
gitignored - it's embedded directly in the README so the map renders on the
GitHub repository homepage.

Mode-aware: sample mode's choropleth is by NUTS2 region (matching the
point-level spatial join). Real mode's is by country (matching the
country-level attribute join - see assign_nuts.py), using NUTS2 polygons
dissolved up to country boundaries.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

try:
    from src import config
    from src.assign_nuts import assign_country_region, assign_nuts_regions, get_region_names, load_nuts_boundaries
    from src.load_lending import load_lending_data
    from src.merge_regional import load_regional_indicators, merge_with_regional_indicator
except ImportError:
    import config
    from assign_nuts import assign_country_region, assign_nuts_regions, get_region_names, load_nuts_boundaries
    from load_lending import load_lending_data
    from merge_regional import load_regional_indicators, merge_with_regional_indicator

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
CHOROPLETH_PATH = OUTPUTS_DIR / "choropleth.png"
CHOROPLETH_PREVIEW_PATH = OUTPUTS_DIR / "choropleth_preview.png"
BY_SECTOR_PATH = OUTPUTS_DIR / "by_sector.png"
OVER_TIME_PATH = OUTPUTS_DIR / "over_time.png"


def _country_polygons(nuts_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Dissolve NUTS2 polygons up to country-level polygons (used for the real-mode choropleth)."""
    nuts2 = nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == 2, ["CNTR_CODE", "geometry"]]
    dissolved = nuts2.dissolve(by="CNTR_CODE", as_index=False)
    return dissolved.rename(columns={"CNTR_CODE": "nuts_code"})


def plot_choropleth(
    panel: pd.DataFrame,
    nuts_gdf: gpd.GeoDataFrame,
    mode: str = "sample",
    output_path: Path = CHOROPLETH_PATH,
    preview_path: Path | None = CHOROPLETH_PREVIEW_PATH,
) -> None:
    """Plot total climate-relevant lending intensity as a choropleth."""
    year_min, year_max = int(panel["year"].min()), int(panel["year"].max())

    if mode == "sample":
        regions = nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == 2, ["NUTS_ID", "NUTS_NAME", "geometry"]]
        regions = regions.rename(columns={"NUTS_ID": "nuts_code"})
        title = f"Green Lending Intensity by NUTS2 Region, {year_min}-{year_max} (synthetic sample data)"
    else:
        regions = _country_polygons(nuts_gdf)
        title = f"Green Lending Intensity by Country, {year_min}-{year_max} (real EIB data, country-level)"

    totals = panel.groupby("nuts_code", as_index=False)["climate_signed_amount_eur"].sum()
    merged = regions.merge(totals, on="nuts_code", how="left")
    merged["climate_signed_amount_eur"] = merged["climate_signed_amount_eur"].fillna(0)
    merged["climate_signed_amount_eur_m"] = merged["climate_signed_amount_eur"] / 1_000_000

    fig, ax = plt.subplots(figsize=(10, 8))
    merged.plot(
        column="climate_signed_amount_eur_m",
        cmap="Greens",
        legend=True,
        edgecolor="black",
        linewidth=0.5,
        ax=ax,
        legend_kwds={"label": "Total climate-relevant lending (EUR millions)"},
    )
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    if preview_path is not None:
        fig.savefig(preview_path, dpi=80)
    plt.close(fig)


def plot_by_sector(lending_df: pd.DataFrame, mode: str = "sample", output_path: Path = BY_SECTOR_PATH) -> None:
    """Plot total signed lending amount by sector as a bar chart."""
    totals = (
        lending_df.groupby("sector", as_index=False)["signed_amount_eur"]
        .sum()
        .sort_values("signed_amount_eur", ascending=False)
    )
    totals["signed_amount_eur_m"] = totals["signed_amount_eur"] / 1_000_000

    label = "synthetic sample data" if mode == "sample" else "real EIB data"
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(totals["sector"], totals["signed_amount_eur_m"], color="#2E7D32")
    ax.set_ylabel("Total signed amount (EUR millions)")
    ax.set_title(f"Green Lending by Sector ({label})")
    ax.tick_params(axis="x", rotation=30)
    for tick_label in ax.get_xticklabels():
        tick_label.set_ha("right")
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_over_time(lending_df: pd.DataFrame, mode: str = "sample", output_path: Path = OVER_TIME_PATH) -> None:
    """Plot total lending per year, all sectors vs. climate-relevant only, as a line chart."""
    yearly_total = lending_df.groupby("signed_year")["signed_amount_eur"].sum()
    yearly_climate = (
        lending_df.loc[lending_df["climate_action"]].groupby("signed_year")["signed_amount_eur"].sum()
    )
    yearly = pd.DataFrame({"total": yearly_total, "climate_total": yearly_climate}).fillna(0)
    yearly = yearly.sort_index()

    label = "synthetic sample data" if mode == "sample" else "real EIB data"
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(yearly.index, yearly["total"] / 1_000_000, marker="o", markersize=3, label="All sectors")
    ax.plot(yearly.index, yearly["climate_total"] / 1_000_000, marker="o", markersize=3, label="Climate-relevant only")
    ax.set_xlabel("Year")
    ax.set_ylabel("Total signed amount (EUR millions)")
    ax.set_title(f"Green Lending Over Time ({label})")
    ax.legend()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Build the lending/region/regional panel in-memory and render all three charts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "real"], default=None,
                         help="Data mode. Defaults to auto-detect (real if data/real/ is fully populated).")
    args = parser.parse_args()
    resolved_mode = config.resolve_mode(args.mode)
    print(f"Mode: {resolved_mode}")

    lending = load_lending_data(mode=resolved_mode)
    nuts_gdf = load_nuts_boundaries(mode=resolved_mode)
    if resolved_mode == "sample":
        lending_with_nuts = assign_nuts_regions(lending, nuts_gdf)
    else:
        lending_with_nuts = assign_country_region(lending, nuts_gdf)
    region_names = get_region_names(resolved_mode, nuts_gdf)
    regional = load_regional_indicators(mode=resolved_mode)
    panel = merge_with_regional_indicator(lending_with_nuts, regional, region_names)

    plot_choropleth(panel, nuts_gdf, mode=resolved_mode)
    print(f"Saved {CHOROPLETH_PATH}")
    print(f"Saved {CHOROPLETH_PREVIEW_PATH}")

    plot_by_sector(lending, mode=resolved_mode)
    print(f"Saved {BY_SECTOR_PATH}")

    plot_over_time(lending, mode=resolved_mode)
    print(f"Saved {OVER_TIME_PATH}")


if __name__ == "__main__":
    main()
