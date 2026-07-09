"""Extract key financial variables from EIB-style project appraisal PDFs.

Uses pdfplumber to pull plain text out of each PDF, then regexes out
financial figures. Mode-aware, because the two document types are genuinely
different:

- Sample mode: synthetic PDFs with three clearly labelled EUR figures
  (total project cost, EIB finance, co-financing) - all three are always
  present and extraction is strict (raises if any is missing).
- Real mode: real EIB "Environmental and Social Data Sheet" (ESDS)
  documents, the only PDF type consistently attached to public EIB
  projects. These are environmental/social compliance sheets, not
  financial appraisals - EIB does not publish per-project EIB-finance /
  co-financing splits in them. In practice only a minority mention a total
  project cost at all, and only in narrative prose (e.g. "total project
  investment cost of EUR 200m"), not a labelled field. Real-mode extraction
  is therefore best-effort: it pulls project_number/project_name/country
  (always present) and total_project_cost_eur when mentioned, and leaves it
  as NaN rather than failing when it isn't - this gap is a genuine, honestly
  reported real-data finding, not a bug.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
import pdfplumber

try:
    from src import config
except ImportError:
    import config

# --- sample mode: strict, all three fields always present ---

SAMPLE_FIELD_PATTERNS = {
    "project_id": re.compile(r"Project ID:\s*(\S+)", re.IGNORECASE),
    "total_project_cost_eur": re.compile(r"Total project cost:\s*EUR\s*([\d,]+)", re.IGNORECASE),
    "eib_finance_eur": re.compile(r"EIB finance:\s*EUR\s*([\d,]+)", re.IGNORECASE),
    "cofinancing_eur": re.compile(r"Co-financing:\s*EUR\s*([\d,]+)", re.IGNORECASE),
}

# --- real mode: lenient, best-effort ---

REAL_ID_PATTERNS = {
    "project_number": re.compile(r"Project Number:\s*(\S+)", re.IGNORECASE),
    "project_name": re.compile(r"Project Name:\s*(.+)", re.IGNORECASE),
    "country": re.compile(r"Country:\s*(.+)", re.IGNORECASE),
}

# Matches narrative mentions like "total project investment cost of EUR 200m"
# or "total cost of EUR 1.2 billion" - real ESDS documents state this (when
# they state it at all) in prose, not a labelled field.
REAL_COST_PATTERN = re.compile(
    r"total[\w\s]{0,30}cost[s]?\s+of\s+EUR\s*([\d.,]+)\s*(million|billion|bn|m|k)?",
    re.IGNORECASE,
)

_UNIT_MULTIPLIERS = {"k": 1_000, "m": 1_000_000, "million": 1_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000}


def _parse_amount(raw: str) -> float:
    """Convert a comma-formatted figure like '145,000,000' to a float."""
    return float(raw.replace(",", ""))


def _parse_narrative_amount(raw: str, unit: str | None) -> float:
    """Convert a narrative figure + optional unit suffix (e.g. '200', 'm') to EUR."""
    value = float(raw.replace(",", ""))
    if unit:
        value *= _UNIT_MULTIPLIERS[unit.lower()]
    return value


def extract_fields_from_pdf(path: Path) -> dict:
    """Extract project_id and the three EUR figures from a synthetic sample PDF.

    Raises ValueError if any of the four expected fields cannot be found -
    the sample documents always contain all four by construction, so a
    missing field means something is genuinely wrong.
    """
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    result: dict = {"source_file": path.name}
    for field, pattern in SAMPLE_FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            raise ValueError(f"could not find '{field}' in {path.name}")
        raw = match.group(1)
        result[field] = raw if field == "project_id" else _parse_amount(raw)

    return result


def extract_real_fields_from_pdf(path: Path) -> dict:
    """Best-effort extraction from a real EIB ESDS PDF.

    project_number, project_name and country are always present in this
    document type and are extracted directly. total_project_cost_eur is
    only present in narrative form in a minority of documents; when absent
    the field is NaN rather than raising, since that reflects the real
    publication practice, not an extraction failure.
    """
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    result: dict = {"source_file": path.name}
    for field, pattern in REAL_ID_PATTERNS.items():
        match = pattern.search(text)
        result[field] = match.group(1).strip() if match else None

    cost_match = REAL_COST_PATTERN.search(text)
    result["total_project_cost_eur"] = (
        _parse_narrative_amount(*cost_match.groups()) if cost_match else float("nan")
    )
    return result


def extract_all_pdfs(mode: str | None = None) -> pd.DataFrame:
    """Extract fields from every PDF for the given (or auto-detected) mode."""
    resolved_mode = config.resolve_mode(mode)
    pdf_dir = config.get_paths(resolved_mode).pdf_dir
    paths = sorted(pdf_dir.glob("*.pdf"))
    if not paths:
        raise FileNotFoundError(f"no PDFs found in {pdf_dir}")

    if resolved_mode == "sample":
        rows = [extract_fields_from_pdf(path) for path in paths]
        cols = ["project_id", "source_file", "total_project_cost_eur", "eib_finance_eur", "cofinancing_eur"]
    else:
        rows = [extract_real_fields_from_pdf(path) for path in paths]
        cols = ["project_number", "project_name", "country", "source_file", "total_project_cost_eur"]

    return pd.DataFrame(rows)[cols]


def main() -> None:
    """Extract fields from all PDFs for the given mode and print the resulting table."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["sample", "real"], default=None,
                         help="Data mode. Defaults to auto-detect (real if data/real/ is fully populated).")
    args = parser.parse_args()
    resolved_mode = config.resolve_mode(args.mode)
    pdf_dir = config.get_paths(resolved_mode).pdf_dir

    df = extract_all_pdfs(mode=resolved_mode)
    print(f"Mode: {resolved_mode}")
    print(f"Extracted fields from {len(df)} PDFs in {pdf_dir}")
    print()
    print(df.to_string(index=False))

    if resolved_mode == "sample":
        reconstructed = df["eib_finance_eur"] + df["cofinancing_eur"]
        mismatch = (reconstructed - df["total_project_cost_eur"]).abs() > 1.0
        if mismatch.any():
            print()
            print("Warning: EIB finance + co-financing does not match total cost for:")
            print(df.loc[mismatch, "project_id"].tolist())
    else:
        found = df["total_project_cost_eur"].notna().sum()
        print()
        print(f"total_project_cost_eur found in {found} / {len(df)} real PDFs.")
        print("EIB does not publicly disclose per-project EIB-finance / co-financing splits in")
        print("this document type, so those two fields are not extracted here - see README.")


if __name__ == "__main__":
    main()
