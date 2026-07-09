"""Assign each lending project a NUTS2 and NUTS3 region via a spatial join.

Takes the point locations (lat/lon) from the lending data and performs a
point-in-polygon join against a NUTS boundaries file that contains both
LEVL_CODE 2 and LEVL_CODE 3 polygons (matching the structure of real GISCO
NUTS boundary files). CRS handling is explicit throughout: both the project
points and the NUTS polygons are treated as EPSG:4326 (WGS84 lat/lon).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd

try:
    from src.load_lending import load_lending_data
except ImportError:
    from load_lending import load_lending_data

DEFAULT_NUTS_PATH = Path(__file__).resolve().parent.parent / "data" / "sample" / "nuts_boundaries.geojson"
CRS = "EPSG:4326"


def load_nuts_boundaries(path: Path | str = DEFAULT_NUTS_PATH) -> gpd.GeoDataFrame:
    """Load the NUTS boundaries file and ensure it is in EPSG:4326."""
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        raise ValueError(f"NUTS boundaries file at {path} has no CRS set")
    if gdf.crs.to_string() != CRS:
        gdf = gdf.to_crs(CRS)
    return gdf


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

    Returns a plain pandas DataFrame (the point geometry is dropped after
    the join - only the codes are needed downstream) with four new columns:
    nuts2_code, nuts2_name, nuts3_code, nuts3_name. Projects whose point
    doesn't fall inside any polygon get NaN in these columns rather than
    being silently dropped.
    """
    points = gpd.GeoDataFrame(
        lending_df.copy(),
        geometry=gpd.points_from_xy(lending_df["lon"], lending_df["lat"]),
        crs=CRS,
    )

    joined = _sjoin_level(points, nuts_gdf, level=2, code_col="nuts2_code", name_col="nuts2_name")
    joined = _sjoin_level(joined, nuts_gdf, level=3, code_col="nuts3_code", name_col="nuts3_name")

    result = pd.DataFrame(joined.drop(columns="geometry"))
    return result.reset_index(drop=True)


def main() -> None:
    """Load the sample lending data and NUTS boundaries, then assign regions."""
    lending = load_lending_data()
    nuts = load_nuts_boundaries()
    print(f"Loaded {len(lending)} projects and {len(nuts)} NUTS polygons")

    result = assign_nuts_regions(lending, nuts)

    unmatched_2 = result["nuts2_code"].isna().sum()
    unmatched_3 = result["nuts3_code"].isna().sum()
    print(f"Unmatched at NUTS2: {unmatched_2} / {len(result)}")
    print(f"Unmatched at NUTS3: {unmatched_3} / {len(result)}")
    print()
    print(result[["project_id", "country", "lat", "lon", "nuts2_code", "nuts3_code"]].head(10).to_string(index=False))
    print()
    print("Projects per NUTS2 region:")
    print(result["nuts2_code"].value_counts())


if __name__ == "__main__":
    main()
