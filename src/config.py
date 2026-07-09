"""Mode selection and path configuration for the eib-green-lending pipeline.

Every pipeline stage resolves its input paths through get_paths(mode) here,
rather than hardcoding data/sample/ or data/real/ directly. This is the only
file that should need editing to add a new data mode or move a real-data
directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"
REAL_DIR = PROJECT_ROOT / "data" / "real"


@dataclass(frozen=True)
class Paths:
    """Resolved input paths for one pipeline run."""

    mode: str
    lending_path: Path
    nuts2_path: Path
    nuts3_path: Path
    regional_path: Path
    pdf_dir: Path


def real_data_available() -> bool:
    """Check whether the full set of real-data files is present under data/real/."""
    return (
        (REAL_DIR / "eib" / "eib_projects.csv").exists()
        and (REAL_DIR / "gisco" / "nuts2_2021.geojson").exists()
        and (REAL_DIR / "gisco" / "nuts3_2021.geojson").exists()
        and (REAL_DIR / "eurostat" / "nama_10r_2gdp.csv").exists()
    )


def resolve_mode(mode: str | None = None) -> str:
    """Resolve the requested mode: honour an explicit choice, else auto-detect.

    Defaults to "real" if the full set of real-data files is present under
    data/real/, otherwise falls back to "sample" so the pipeline always runs
    without requiring any downloads.
    """
    if mode is not None:
        if mode not in ("sample", "real"):
            raise ValueError(f"mode must be 'sample' or 'real', got {mode!r}")
        return mode
    return "real" if real_data_available() else "sample"


def get_paths(mode: str | None = None) -> Paths:
    """Return the resolved Paths for the given (or auto-detected) mode."""
    resolved = resolve_mode(mode)
    if resolved == "real":
        return Paths(
            mode="real",
            lending_path=REAL_DIR / "eib" / "eib_projects.csv",
            nuts2_path=REAL_DIR / "gisco" / "nuts2_2021.geojson",
            nuts3_path=REAL_DIR / "gisco" / "nuts3_2021.geojson",
            regional_path=REAL_DIR / "eurostat" / "nama_10r_2gdp.csv",
            pdf_dir=REAL_DIR / "eib" / "pdfs",
        )
    return Paths(
        mode="sample",
        lending_path=SAMPLE_DIR / "lending.csv",
        nuts2_path=SAMPLE_DIR / "nuts_boundaries.geojson",
        nuts3_path=SAMPLE_DIR / "nuts_boundaries.geojson",
        regional_path=SAMPLE_DIR / "regional_indicators.csv",
        pdf_dir=SAMPLE_DIR / "pdfs",
    )
