"""Produce the pipeline's three visualisations from the lending and panel data.

Generates:
- outputs/choropleth.png       total climate-relevant lending intensity per NUTS2 region
- outputs/by_sector.png        total lending by sector (all sectors, not just climate-relevant)
- outputs/over_time.png        total lending over time, all sectors vs. climate-relevant only

Also saves a smaller preview copy of the choropleth to
outputs/choropleth_preview.png, which is the one exception to outputs/ being
gitignored - it's embedded directly in the README so the map renders on the
GitHub repository homepage.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd

try:
    from src.assign_nuts import assign_nuts_regions, load_nuts_boundaries
    from src.load_lending import load_lending_data
    from src.merge_regional import load_regional_indicators, merge_with_regional_indicator
except ImportError:
    from assign_nuts import assign_nuts_regions, load_nuts_boundaries
    from load_lending import load_lending_data
    from merge_regional import load_regional_indicators, merge_with_regional_indicator

OUTPUTS_DIR = Path(__file__).resolve().parent.parent / "outputs"
CHOROPLETH_PATH = OUTPUTS_DIR / "choropleth.png"
CHOROPLETH_PREVIEW_PATH = OUTPUTS_DIR / "choropleth_preview.png"
BY_SECTOR_PATH = OUTPUTS_DIR / "by_sector.png"
OVER_TIME_PATH = OUTPUTS_DIR / "over_time.png"


def plot_choropleth(
    panel: pd.DataFrame,
    nuts_gdf: gpd.GeoDataFrame,
    output_path: Path = CHOROPLETH_PATH,
    preview_path: Path | None = CHOROPLETH_PREVIEW_PATH,
) -> None:
    """Plot total climate-relevant lending (2014-2023) per NUTS2 region as a choropleth."""
    nuts2 = nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == 2, ["NUTS_ID", "NUTS_NAME", "geometry"]]
    nuts2 = nuts2.rename(columns={"NUTS_ID": "nuts_code"})

    totals = panel.groupby("nuts_code", as_index=False)["climate_signed_amount_eur"].sum()
    merged = nuts2.merge(totals, on="nuts_code", how="left")
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
        legend_kwds={"label": "Total climate-relevant lending, 2014-2023 (EUR millions)"},
    )
    ax.set_title("Green Lending Intensity by NUTS2 Region (synthetic sample data)")
    ax.set_axis_off()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    if preview_path is not None:
        fig.savefig(preview_path, dpi=80)
    plt.close(fig)


def plot_by_sector(lending_df: pd.DataFrame, output_path: Path = BY_SECTOR_PATH) -> None:
    """Plot total signed lending amount by sector as a bar chart."""
    totals = (
        lending_df.groupby("sector", as_index=False)["signed_amount_eur"]
        .sum()
        .sort_values("signed_amount_eur", ascending=False)
    )
    totals["signed_amount_eur_m"] = totals["signed_amount_eur"] / 1_000_000

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(totals["sector"], totals["signed_amount_eur_m"], color="#2E7D32")
    ax.set_ylabel("Total signed amount (EUR millions)")
    ax.set_title("Green Lending by Sector (synthetic sample data)")
    ax.tick_params(axis="x", rotation=30)
    for label in ax.get_xticklabels():
        label.set_ha("right")
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_over_time(lending_df: pd.DataFrame, output_path: Path = OVER_TIME_PATH) -> None:
    """Plot total lending per year, all sectors vs. climate-relevant only, as a line chart."""
    yearly_total = lending_df.groupby("signed_year")["signed_amount_eur"].sum()
    yearly_climate = (
        lending_df.loc[lending_df["climate_action"]].groupby("signed_year")["signed_amount_eur"].sum()
    )
    yearly = pd.DataFrame({"total": yearly_total, "climate_total": yearly_climate}).fillna(0)
    yearly = yearly.sort_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(yearly.index, yearly["total"] / 1_000_000, marker="o", label="All sectors")
    ax.plot(yearly.index, yearly["climate_total"] / 1_000_000, marker="o", label="Climate-relevant only")
    ax.set_xlabel("Year")
    ax.set_ylabel("Total signed amount (EUR millions)")
    ax.set_title("Green Lending Over Time (synthetic sample data)")
    ax.legend()
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Build the lending/NUTS/regional panel in-memory and render all three charts."""
    lending = load_lending_data()
    nuts_gdf = load_nuts_boundaries()
    lending_with_nuts = assign_nuts_regions(lending, nuts_gdf)
    regional = load_regional_indicators()
    panel = merge_with_regional_indicator(lending_with_nuts, regional, nuts_gdf)

    plot_choropleth(panel, nuts_gdf)
    print(f"Saved {CHOROPLETH_PATH}")
    print(f"Saved {CHOROPLETH_PREVIEW_PATH}")

    plot_by_sector(lending)
    print(f"Saved {BY_SECTOR_PATH}")

    plot_over_time(lending)
    print(f"Saved {OVER_TIME_PATH}")


if __name__ == "__main__":
    main()
