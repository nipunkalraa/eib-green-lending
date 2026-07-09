"""Generate a small, seeded synthetic sample dataset for the eib-green-lending pipeline.

Creates, under data/sample/:
- lending.csv               EIB-style green-lending project records
- nuts_boundaries.geojson   fake rectangular NUTS2/NUTS3 regions covering parts of Europe
- regional_indicators.csv   Eurostat-style regional indicator panel (NUTS2 x year)
- pdfs/*.pdf                a handful of EIB-style project appraisal PDFs

Every value here is synthetic and generated with a fixed random seed so that
repeated runs produce identical output. Nothing in this module touches the
network or reads real EIB/Eurostat/GISCO data - see data/real/ and the
README's Phase 2 section for wiring in the real sources later.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from shapely.geometry import box

SEED = 42
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
PDF_DIR = DATA_DIR / "pdfs"

# country_code -> (name, lon_min, lon_max, lat_min, lat_max, cities)
# Bounding boxes are loosely-Europe-shaped but not surveyed boundaries - they
# exist only so synthetic project points and synthetic NUTS rectangles agree
# with each other.
COUNTRIES = {
    "PT": ("Portugal", -9.5, -6.5, 37.0, 42.0, ["Lisbon", "Porto"]),
    "ES": ("Spain", -6.5, 1.5, 36.0, 43.0, ["Madrid", "Barcelona", "Valencia"]),
    "IT": ("Italy", 6.5, 14.0, 37.0, 44.5, ["Rome", "Milan", "Turin"]),
    "EL": ("Greece", 20.0, 26.5, 36.0, 41.5, ["Athens", "Thessaloniki"]),
    "RO": ("Romania", 21.0, 28.5, 43.5, 48.0, ["Bucharest", "Cluj-Napoca"]),
    "IE": ("Ireland", -10.0, -6.0, 51.5, 55.0, ["Dublin", "Cork"]),
    "FR": ("France", -1.5, 6.0, 44.0, 50.5, ["Paris", "Lyon", "Marseille"]),
    "DE": ("Germany", 7.0, 14.5, 48.0, 54.5, ["Berlin", "Munich", "Hamburg"]),
    "PL": ("Poland", 15.0, 23.0, 49.5, 54.5, ["Warsaw", "Krakow"]),
    "SE": ("Sweden", 12.0, 22.0, 55.5, 65.0, ["Stockholm", "Gothenburg"]),
}

GREEN_SECTORS = ["Renewable Energy", "Energy Efficiency", "Clean Transport", "Water Management"]
OTHER_SECTORS = ["Industry", "Urban Infrastructure"]

NAME_TEMPLATES = [
    "{sector} Investment Programme - {city}",
    "{city} {sector} Initiative",
    "{sector} Upgrade - {country}",
    "{sector} Facility, {city}",
]

YEARS = range(2014, 2024)


def generate_lending_data(rng: np.random.Generator, n: int = 200) -> pd.DataFrame:
    """Generate a synthetic EIB-style green-lending project table.

    Produces `n` rows spanning the ten synthetic countries in COUNTRIES,
    signed years 2014-2023, and a mix of green and non-green sectors so the
    climate_action column can be used to demonstrate filtering.
    """
    country_codes = list(COUNTRIES.keys())
    rows = []
    for i in range(n):
        cc = rng.choice(country_codes)
        name, lon_min, lon_max, lat_min, lat_max, cities = COUNTRIES[cc]
        city = rng.choice(cities)
        is_green = rng.random() < 0.8
        sector = rng.choice(GREEN_SECTORS) if is_green else rng.choice(OTHER_SECTORS)
        template = rng.choice(NAME_TEMPLATES)
        project_name = str(template).format(sector=sector, city=city, country=name)
        signed_year = int(rng.integers(2014, 2024))
        # inset the sampling box slightly so points never land on a region edge
        lon = rng.uniform(lon_min + 0.2, lon_max - 0.2)
        lat = rng.uniform(lat_min + 0.2, lat_max - 0.2)
        amount = float(
            np.clip(rng.lognormal(mean=np.log(50_000_000), sigma=0.7), 5_000_000, 500_000_000)
        )
        rows.append(
            {
                "project_id": f"EIB-{signed_year}-{i:04d}",
                "project_name": project_name,
                "country": cc,
                "city": city,
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "signed_amount_eur": round(amount, -5),
                "sector": sector,
                "climate_action": bool(is_green),
                "signed_year": signed_year,
            }
        )
    return pd.DataFrame(rows)


def generate_nuts_boundaries() -> gpd.GeoDataFrame:
    """Generate a small set of fake, simple rectangular NUTS2/NUTS3 regions.

    Each synthetic country becomes exactly one NUTS2 rectangle, split down
    the middle into two NUTS3 halves. This mirrors the nesting convention of
    real GISCO NUTS boundary files (a NUTS3 code is its parent NUTS2 code
    plus one extra digit) while staying trivial to construct and reason
    about.
    """
    records = []
    for cc, (name, lon_min, lon_max, lat_min, lat_max, _) in COUNTRIES.items():
        nuts2_id = f"{cc}10"
        records.append(
            {
                "NUTS_ID": nuts2_id,
                "NUTS_NAME": f"{name} (synthetic NUTS2)",
                "LEVL_CODE": 2,
                "CNTR_CODE": cc,
                "geometry": box(lon_min, lat_min, lon_max, lat_max),
            }
        )
        lon_mid = (lon_min + lon_max) / 2
        records.append(
            {
                "NUTS_ID": f"{nuts2_id}1",
                "NUTS_NAME": f"{name} West (synthetic NUTS3)",
                "LEVL_CODE": 3,
                "CNTR_CODE": cc,
                "geometry": box(lon_min, lat_min, lon_mid, lat_max),
            }
        )
        records.append(
            {
                "NUTS_ID": f"{nuts2_id}2",
                "NUTS_NAME": f"{name} East (synthetic NUTS3)",
                "LEVL_CODE": 3,
                "CNTR_CODE": cc,
                "geometry": box(lon_mid, lat_min, lon_max, lat_max),
            }
        )
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def generate_regional_indicators(rng: np.random.Generator, years=YEARS) -> pd.DataFrame:
    """Generate a synthetic Eurostat-style NUTS2 regional indicator panel.

    Produces one row per (NUTS2 region, year) with a gross-fixed-capital-
    formation-style indicator (gfcf_eur_millions) that mirrors the "gross
    fixed capital formation (NUTS2)" series named in Eurostat regional
    accounts. Values follow a mild upward trend plus noise per region so the
    panel looks like a plausible (but entirely synthetic) regional economic
    series - it is illustrative only, not a real economic estimate.
    """
    rows = []
    for cc in COUNTRIES:
        nuts2_id = f"{cc}10"
        base = rng.uniform(8_000, 60_000)  # EUR millions
        for idx, year in enumerate(years):
            trend = 1 + 0.02 * idx
            noise = rng.uniform(0.92, 1.08)
            value = base * trend * noise
            rows.append(
                {
                    "nuts_code": nuts2_id,
                    "year": year,
                    "gfcf_eur_millions": round(value, 1),
                }
            )
    return pd.DataFrame(rows)


def generate_project_pdfs(
    lending_df: pd.DataFrame, rng: np.random.Generator, out_dir: Path, n: int = 5
) -> None:
    """Generate a handful of synthetic EIB-style project appraisal PDFs.

    Picks `n` projects from `lending_df` and writes a short appraisal-style
    PDF for each, containing "Total project cost", "EIB finance" and
    "Co-financing" lines with EUR figures - the fields extract_pdf.py later
    parses back out with pdfplumber. This exists to demonstrate the
    extraction machinery, not to model a realistic corpus size.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_idx = rng.choice(lending_df.index, size=n, replace=False)

    for idx in sample_idx:
        row = lending_df.loc[idx]
        total_cost = round(float(rng.uniform(50_000_000, 300_000_000)), -5)
        eib_share = rng.uniform(0.3, 0.5)
        eib_finance = round(total_cost * eib_share, -5)
        cofinancing = total_cost - eib_finance

        path = out_dir / f"{row['project_id']}.pdf"
        c = canvas.Canvas(str(path), pagesize=A4)
        _, height = A4
        text = c.beginText(50, height - 60)
        text.setFont("Helvetica-Bold", 13)
        text.textLine("Project Appraisal Summary")
        text.setFont("Helvetica", 10)
        text.textLine("")
        text.textLine(f"Project ID: {row['project_id']}")
        text.textLine(f"Project Name: {row['project_name']}")
        text.textLine(f"Sector: {row['sector']}")
        text.textLine(f"Country: {row['country']}")
        text.textLine("")

        narrative = (
            f"This appraisal covers the proposed financing of a {row['sector'].lower()} "
            f"project located in {row['city']}, {row['country']}. The investment is "
            "expected to support the Bank's climate action objectives and to crowd in "
            "additional co-financing from national and private sources."
        )
        for line in textwrap.wrap(narrative, width=90):
            text.textLine(line)
        text.textLine("")

        text.textLine(f"Total project cost: EUR {total_cost:,.0f}")
        text.textLine(f"EIB finance: EUR {eib_finance:,.0f}")
        text.textLine(f"Co-financing: EUR {cofinancing:,.0f}")

        c.drawText(text)
        c.showPage()
        c.save()


def main() -> None:
    """Generate and write all synthetic sample inputs under data/sample/."""
    rng = np.random.default_rng(SEED)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic lending data...")
    lending = generate_lending_data(rng)
    lending.to_csv(DATA_DIR / "lending.csv", index=False)
    print(f"  wrote {len(lending)} rows to {DATA_DIR / 'lending.csv'}")

    print("Generating synthetic NUTS boundaries...")
    nuts = generate_nuts_boundaries()
    nuts.to_file(DATA_DIR / "nuts_boundaries.geojson", driver="GeoJSON")
    print(f"  wrote {len(nuts)} regions to {DATA_DIR / 'nuts_boundaries.geojson'}")

    print("Generating synthetic regional indicators...")
    regional = generate_regional_indicators(rng)
    regional.to_csv(DATA_DIR / "regional_indicators.csv", index=False)
    print(f"  wrote {len(regional)} rows to {DATA_DIR / 'regional_indicators.csv'}")

    print("Generating synthetic project PDFs...")
    generate_project_pdfs(lending, rng, PDF_DIR)
    print(f"  wrote {len(list(PDF_DIR.glob('*.pdf')))} PDFs to {PDF_DIR}")

    print("Done.")


if __name__ == "__main__":
    main()
