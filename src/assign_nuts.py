"""Assign each lending project a NUTS2 (or country-level) region.

Sample mode: takes point locations (lat/lon) from the synthetic lending data
and performs a genuine point-in-polygon join against NUTS boundaries with
geopandas.sjoin, producing both NUTS2 and NUTS3 codes. CRS handling is
explicit throughout: both the project points and the NUTS polygons are
treated as EPSG:4326 (WGS84 lat/lon).

Real mode: the real EIB export has no project-level coordinates (see
load_lending.py), so a spatial point-in-polygon join isn't possible. Instead
assign_country_region does a plain attribute join on the project's country
name, resolved to GISCO's country-code convention. This is a real, honest
reduction in granularity compared to sample mode - documented in the README
- not an attempt to fake point-level precision that the public data doesn't
support.

Mode-aware boundary loading: sample mode reads a single combined GeoJSON
with an existing LEVL_CODE column (see generate_synthetic.py). Real mode
reads two separate Nuts2json GeoJSON files (one per level, from GISCO),
whose `id`/`na` properties are standardized onto the same NUTS_ID/NUTS_NAME/
LEVL_CODE/CNTR_CODE schema used by sample mode.
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd
import pycountry

try:
    from src import config
    from src.load_lending import load_lending_data
except ImportError:
    import config
    from load_lending import load_lending_data

CRS = "EPSG:4326"

# GISCO/Eurostat's NUTS country-code convention deviates from ISO 3166-1 for
# these two: Greece is "EL" (not ISO's "GR") and the United Kingdom is "UK"
# (not ISO's "GB"). Real GISCO NUTS2021 data still includes UK regions.
ISO_TO_GISCO_OVERRIDES = {"GR": "EL", "GB": "UK"}


def _standardize_nuts2json(gdf: gpd.GeoDataFrame, level: int) -> gpd.GeoDataFrame:
    """Standardize a Nuts2json GeoJSON (id/na properties) onto the internal NUTS schema."""
    gdf = gdf.rename(columns={"id": "NUTS_ID", "na": "NUTS_NAME"})
    gdf["LEVL_CODE"] = level
    gdf["CNTR_CODE"] = gdf["NUTS_ID"].str[:2]
    return gdf[["NUTS_ID", "NUTS_NAME", "LEVL_CODE", "CNTR_CODE", "geometry"]]


def load_nuts_boundaries(mode: str | None = None) -> gpd.GeoDataFrame:
    """Load NUTS boundaries for the given (or auto-detected) mode, standardized to EPSG:4326.

    Sample mode reads a single combined file with an existing LEVL_CODE
    column. Real mode reads two separate Nuts2json GeoJSON files (one per
    level) and standardizes them onto the same schema.
    """
    resolved_mode = config.resolve_mode(mode)
    paths = config.get_paths(resolved_mode)

    if resolved_mode == "sample":
        gdf = gpd.read_file(paths.nuts2_path)
    else:
        gdf2 = _standardize_nuts2json(gpd.read_file(paths.nuts2_path), level=2)
        gdf3 = _standardize_nuts2json(gpd.read_file(paths.nuts3_path), level=3)
        gdf = gpd.GeoDataFrame(pd.concat([gdf2, gdf3], ignore_index=True), geometry="geometry")

    if gdf.crs is None:
        raise ValueError(f"NUTS boundaries for mode {resolved_mode!r} have no CRS set")
    if gdf.crs.to_string() != CRS:
        gdf = gdf.to_crs(CRS)
    return gdf


def get_region_names(mode: str, nuts_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Return a (nuts_code, nuts_name) lookup at the granularity used by the given mode.

    Sample mode: NUTS2 region names. Real mode: country display names (the
    finest granularity real mode can assign - see assign_country_region).
    """
    if mode == "sample":
        return (
            nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == 2, ["NUTS_ID", "NUTS_NAME"]]
            .rename(columns={"NUTS_ID": "nuts_code", "NUTS_NAME": "nuts_name"})
            .reset_index(drop=True)
        )
    gisco_to_iso = {v: k for k, v in ISO_TO_GISCO_OVERRIDES.items()}
    rows = []
    for code in sorted(nuts_gdf["CNTR_CODE"].unique()):
        iso_code = gisco_to_iso.get(code, code)
        country = pycountry.countries.get(alpha_2=iso_code)
        rows.append({"nuts_code": code, "nuts_name": country.name if country else code})
    return pd.DataFrame(rows)


def _country_name_to_gisco_code(name: str) -> str | None:
    """Resolve a free-text country name (as used in the real EIB export) to a GISCO country code."""
    if pd.isna(name):
        return None
    match = None
    try:
        match = pycountry.countries.lookup(name)
    except LookupError:
        try:
            matches = pycountry.countries.search_fuzzy(name)
            match = matches[0] if matches else None
        except LookupError:
            match = None
    if match is None:
        return None
    return ISO_TO_GISCO_OVERRIDES.get(match.alpha_2, match.alpha_2)


def _sjoin_level(points: gpd.GeoDataFrame, nuts_gdf: gpd.GeoDataFrame, level: int, code_col: str, name_col: str) -> gpd.GeoDataFrame:
    """Spatial-join `points` against the NUTS polygons at a single LEVL_CODE."""
    level_gdf = nuts_gdf.loc[nuts_gdf["LEVL_CODE"] == level, ["NUTS_ID", "NUTS_NAME", "geometry"]]
    level_gdf = level_gdf.rename(columns={"NUTS_ID": code_col, "NUTS_NAME": name_col})

    joined = gpd.sjoin(points, level_gdf, how="left", predicate="within")
    joined = joined.drop(columns=["index_right"])

    if len(joined) != len(points):
        raise ValueError(
            f"spatial join at LEVL_CODE {level} produced {len(joined)} rows from "
            f"{len(points)} input points - NUTS polygons at this level must overlap"
        )
    return joined


def assign_nuts_regions(lending_df: pd.DataFrame, nuts_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Assign a NUTS2 and NUTS3 code to every project via point-in-polygon joins.

    Projects with a missing lat or lon are dropped before the join (with a
    printed count) rather than causing an error. Projects whose point
    doesn't fall inside any polygon (e.g. off the coast, outside the covered
    area) get NaN in the NUTS columns rather than being silently dropped.

    Returns a plain pandas DataFrame (the point geometry is dropped after
    the join - only the codes are needed downstream) with four new columns:
    nuts2_code, nuts2_name, nuts3_code, nuts3_name.
    """
    missing_coords = lending_df["lat"].isna() | lending_df["lon"].isna()
    n_missing = int(missing_coords.sum())
    if n_missing:
        print(f"Dropping {n_missing} project(s) with missing lat/lon before the spatial join")
    df = lending_df.loc[~missing_coords].copy()

    points = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs=CRS,
    )

    joined = _sjoin_level(points, nuts_gdf, level=2, code_col="nuts2_code", name_col="nuts2_name")
    joined = _sjoin_level(joined, nuts_gdf, level=3, code_col="nuts3_code", name_col="nuts3_name")

    result = pd.DataFrame(joined.drop(columns="geometry"))
    return result.reset_index(drop=True)


def assign_country_region(lending_df: pd.DataFrame, nuts_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Attribute-join lending projects to country-level regions (real mode only).

    The real EIB export has no project-level coordinates, so unlike
    assign_nuts_regions this is not a spatial point-in-polygon join - it's a
    plain lookup on the project's country name, resolved to GISCO's country
    code convention (see _country_name_to_gisco_code). Only countries
    covered by GISCO NUTS (EU/EFTA/candidate countries) can be matched;
    EIB's global lending outside that scope is reported as unmatched rather
    than guessed. nuts3_code/nuts3_name are not available at this
    granularity and are left as NaN throughout.
    """
    valid_codes = set(nuts_gdf["CNTR_CODE"].unique())
    names = get_region_names("real", nuts_gdf).set_index("nuts_code")["nuts_name"]

    df = lending_df.copy()
    resolved = df["country"].apply(_country_name_to_gisco_code)
    df["nuts2_code"] = resolved.where(resolved.isin(valid_codes))
    df["nuts2_name"] = df["nuts2_code"].map(names)
    df["nuts3_code"] = pd.NA
    df["nuts3_name"] = pd.NA

    n_matched = df["nuts2_code"].notna().sum()
    print(f"Country-level match: {n_matched} / {len(df)} projects matched to a NUTS-covered country")
    print(f"  ({df['country'].nunique()} distinct country/territory names in the export; "
          f"{len(valid_codes)} covered by GISCO NUTS)")

    return df.reset_index(drop=True)


def main() -> None:
    """Load lending data and NUTS boundaries for the given mode, then assign regions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "real"], default=None,
                         help="Data mode. Defaults to auto-detect (real if data/real/ is fully populated).")
    args = parser.parse_args()
    resolved_mode = config.resolve_mode(args.mode)

    lending = load_lending_data(mode=resolved_mode)
    nuts = load_nuts_boundaries(mode=resolved_mode)
    print(f"Mode: {resolved_mode}")
    print(f"Loaded {len(lending)} projects and {len(nuts)} NUTS polygons")

    if resolved_mode == "sample":
        result = assign_nuts_regions(lending, nuts)
    else:
        result = assign_country_region(lending, nuts)

    unmatched_2 = result["nuts2_code"].isna().sum()
    print(f"Unmatched at NUTS2/country: {unmatched_2} / {len(result)}")
    if resolved_mode == "sample":
        unmatched_3 = result["nuts3_code"].isna().sum()
        print(f"Unmatched at NUTS3: {unmatched_3} / {len(result)}")
    print()
    print(result[["project_id", "country", "nuts2_code", "nuts3_code"]].head(10).to_string(index=False))
    print()
    print("Projects per NUTS2/country region (top 15):")
    print(result["nuts2_code"].value_counts().head(15))


if __name__ == "__main__":
    main()
