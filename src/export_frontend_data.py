"""Export static data files for the Next.js dashboard in frontend/.

Writes frontend/public/data/nuts_lending.geojson and summary.json from the
same pipeline outputs the other stages produce. This is a one-way boundary:
the Python pipeline does not import anything from frontend/, and the
frontend only ever reads these two static files - no backend, no API
routes. Idempotent: re-running overwrites the same two files.

Mode-aware, same as the rest of the pipeline. Note the honesty caveat this
carries into real mode: the real EIB export has no project coordinates, so
"nuts_lending.geojson" is genuinely NUTS2-level only in sample mode - in
real mode it's country-level (see assign_nuts.assign_country_region and the
README's Known Limitations). The property names (NUTS_ID etc.) are kept
consistent across modes for the frontend's sake, but real mode's NUTS_ID
values are 2-character country codes, not 4-character NUTS2 codes. This is
disclosed in summary.json's "limitations" field and the dashboard's
Methodology section, not hidden.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

try:
    from src import config
    from src.assign_nuts import assign_country_region, assign_nuts_regions, get_region_names, load_nuts_boundaries
    from src.load_lending import load_lending_data
    from src.merge_regional import load_regional_indicators, merge_with_regional_indicator
    from src.visualise import _country_polygons
except ImportError:
    import config
    from assign_nuts import assign_country_region, assign_nuts_regions, get_region_names, load_nuts_boundaries
    from load_lending import load_lending_data
    from merge_regional import load_regional_indicators, merge_with_regional_indicator
    from visualise import _country_polygons

FRONTEND_DATA_DIR = Path(__file__).resolve().parent.parent / "frontend" / "public" / "data"
GEOJSON_PATH = FRONTEND_DATA_DIR / "nuts_lending.geojson"
SUMMARY_PATH = FRONTEND_DATA_DIR / "summary.json"

# ~0.01 degrees (roughly 1km at European latitudes) - keeps the static
# GeoJSON small for a snappy map load without visibly distorting a
# country/NUTS2-scale choropleth.
SIMPLIFY_TOLERANCE_DEG = 0.01

# Kept in sync manually with the README's "Known limitations" section -
# not parsed from the README, to keep this script simple.
REAL_MODE_LIMITATIONS = [
    "Real mode is country-level, not NUTS2/NUTS3: the public EIB financed-projects export has "
    "no project-level coordinates, so regions here are countries, not sub-national NUTS2 areas.",
    "climate_action is a keyword heuristic on Sector/Description text, not an official EIB "
    "classification - the public export exposes no internal Climate Action flag.",
    "PDF-derived financial figures are sparse by design: EIB's public appraisal PDFs are "
    "environmental/social compliance sheets, not financial appraisals, and rarely disclose cost figures.",
    "EIB lends globally; NUTS only covers ~37 European countries, so a meaningful share of real "
    "projects fall outside this map's coverage and are excluded rather than guessed at.",
    "No causal inference or econometric modelling is included - this is data construction and "
    "descriptive visualisation only.",
]


def _top_sectors_by_region(lending_with_region: pd.DataFrame, n: int = 5) -> dict[str, list[dict]]:
    """Group signed_amount_eur by region + sector; return each region's top N sectors."""
    grouped = (
        lending_with_region.groupby(["nuts2_code", "sector"], as_index=False)["signed_amount_eur"]
        .sum()
        .rename(columns={"signed_amount_eur": "total_eur"})
    )
    result: dict[str, list[dict]] = {}
    for code, group in grouped.groupby("nuts2_code"):
        top = group.sort_values("total_eur", ascending=False).head(n)
        result[code] = [
            {"sector": row.sector, "total_eur": round(float(row.total_eur), 2)} for row in top.itertuples()
        ]
    return result


def build_region_geojson(
    lending_with_region: pd.DataFrame,
    panel: pd.DataFrame,
    region_geoms: gpd.GeoDataFrame,
    region_names: pd.DataFrame,
) -> dict:
    """Build the nuts_lending.geojson FeatureCollection.

    `region_geoms` must have columns [nuts_code, geometry]. `panel` is the
    region x year panel from merge_regional.merge_with_regional_indicator.
    """
    totals = panel.groupby("nuts_code", as_index=False).agg(
        total_lending_eur=("total_signed_amount_eur", "sum"),
        project_count=("num_projects", "sum"),
        climate_signed_amount_eur=("climate_signed_amount_eur", "sum"),
    )
    totals["avg_lending_eur"] = (totals["total_lending_eur"] / totals["project_count"]).where(
        totals["project_count"] > 0
    )
    totals["climate_share"] = (totals["climate_signed_amount_eur"] / totals["total_lending_eur"]).where(
        totals["total_lending_eur"] > 0
    )

    top_sectors = _top_sectors_by_region(lending_with_region)

    geoms = region_geoms.copy()
    geoms["geometry"] = geoms["geometry"].simplify(SIMPLIFY_TOLERANCE_DEG, preserve_topology=True)

    merged = geoms.merge(totals, on="nuts_code", how="left")
    merged = merged.merge(region_names, on="nuts_code", how="left")
    merged["total_lending_eur"] = merged["total_lending_eur"].fillna(0)
    merged["project_count"] = merged["project_count"].fillna(0).astype(int)

    features = []
    for row in merged.itertuples():
        code = row.nuts_code
        features.append(
            {
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__,
                "properties": {
                    "NUTS_ID": code,
                    "NUTS_NAME": row.nuts_name if pd.notna(row.nuts_name) else code,
                    "CNTR_CODE": code[:2],
                    "total_lending_eur": round(float(row.total_lending_eur), 2),
                    "project_count": int(row.project_count),
                    "avg_lending_eur": round(float(row.avg_lending_eur), 2) if pd.notna(row.avg_lending_eur) else None,
                    "climate_share": round(float(row.climate_share), 4) if pd.notna(row.climate_share) else None,
                    "top_sectors": top_sectors.get(code, []),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def build_summary(lending_df: pd.DataFrame, panel: pd.DataFrame, mode: str) -> dict:
    """Build the summary.json top-line stats."""
    df = lending_df.copy()
    df["climate_signed_amount_eur"] = df["signed_amount_eur"].where(df["climate_action"], 0.0)

    totals_by_region = panel.groupby(["nuts_code", "nuts_name"], as_index=False)["total_signed_amount_eur"].sum()
    top10 = totals_by_region.sort_values("total_signed_amount_eur", ascending=False).head(10)

    sector_totals = (
        df.groupby("sector", as_index=False)["signed_amount_eur"]
        .sum()
        .sort_values("signed_amount_eur", ascending=False)
    )

    yearly = df.groupby("signed_year", as_index=False).agg(
        total_eur=("signed_amount_eur", "sum"),
        climate_eur=("climate_signed_amount_eur", "sum"),
    )

    return {
        "mode": mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_lending_eur": round(float(df["signed_amount_eur"].sum()), 2),
        "total_projects": int(len(df)),
        "climate_relevant_projects": int(df["climate_action"].sum()),
        "countries_covered": int(panel["nuts_code"].nunique()),
        "year_range": [int(df["signed_year"].min()), int(df["signed_year"].max())],
        "top_regions": [
            {
                "nuts_id": row.nuts_code,
                "nuts_name": row.nuts_name,
                "total_lending_eur": round(float(row.total_signed_amount_eur), 2),
            }
            for row in top10.itertuples()
        ],
        "sector_breakdown": [
            {"sector": row.sector, "total_eur": round(float(row.signed_amount_eur), 2)}
            for row in sector_totals.itertuples()
        ],
        "lending_over_time": [
            {"year": int(row.signed_year), "total_eur": round(float(row.total_eur), 2), "climate_eur": round(float(row.climate_eur), 2)}
            for row in yearly.sort_values("signed_year").itertuples()
        ],
        "limitations": REAL_MODE_LIMITATIONS if mode == "real" else [],
    }


def main() -> None:
    """Run the full pipeline in the given mode and export the two frontend data files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "real"], default=None,
                         help="Data mode. Defaults to auto-detect (real if data/real/ is fully populated).")
    args = parser.parse_args()
    resolved_mode = config.resolve_mode(args.mode)

    lending = load_lending_data(mode=resolved_mode)
    nuts_gdf = load_nuts_boundaries(mode=resolved_mode)

    if resolved_mode == "sample":
        lending_with_region = assign_nuts_regions(lending, nuts_gdf)
        region_geoms = (
            nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == 2, ["NUTS_ID", "geometry"]]
            .rename(columns={"NUTS_ID": "nuts_code"})
        )
    else:
        lending_with_region = assign_country_region(lending, nuts_gdf)
        region_geoms = _country_polygons(nuts_gdf)[["nuts_code", "geometry"]]

    region_names = get_region_names(resolved_mode, nuts_gdf)
    regional = load_regional_indicators(mode=resolved_mode)
    panel = merge_with_regional_indicator(lending_with_region, regional, region_names)

    geojson = build_region_geojson(lending_with_region, panel, region_geoms, region_names)
    summary = build_summary(lending, panel, resolved_mode)

    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Mode: {resolved_mode}")
    print(f"Wrote {len(geojson['features'])} region features to {GEOJSON_PATH}")
    print(f"Wrote summary to {SUMMARY_PATH}")
    print(f"  total_lending_eur: {summary['total_lending_eur']:,.0f}")
    print(f"  total_projects: {summary['total_projects']}")
    print(f"  countries_covered: {summary['countries_covered']}")
    print(f"  year_range: {summary['year_range']}")


if __name__ == "__main__":
    main()
