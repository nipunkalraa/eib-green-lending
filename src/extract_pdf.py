"""Extract key financial variables from EIB-style project appraisal PDFs.

Uses pdfplumber to pull plain text out of each PDF, then regexes out three
labelled EUR figures: total project cost, EIB finance, and co-financing.
This demonstrates the extraction machinery described in the target
role (systematic extraction from project appraisal PDFs) on a small,
synthetic corpus - it is not meant to be a general-purpose PDF parser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pdfplumber

DEFAULT_PDF_DIR = Path(__file__).resolve().parent.parent / "data" / "sample" / "pdfs"

FIELD_PATTERNS = {
    "project_id": re.compile(r"Project ID:\s*(\S+)", re.IGNORECASE),
    "total_project_cost_eur": re.compile(r"Total project cost:\s*EUR\s*([\d,]+)", re.IGNORECASE),
    "eib_finance_eur": re.compile(r"EIB finance:\s*EUR\s*([\d,]+)", re.IGNORECASE),
    "cofinancing_eur": re.compile(r"Co-financing:\s*EUR\s*([\d,]+)", re.IGNORECASE),
}


def _parse_amount(raw: str) -> float:
    """Convert a comma-formatted figure like '145,000,000' to a float."""
    return float(raw.replace(",", ""))


def extract_fields_from_pdf(path: Path) -> dict:
    """Extract project_id and the three EUR figures from a single PDF.

    Raises ValueError if any of the four expected fields cannot be found in
    the PDF text, so a malformed document fails loudly rather than silently
    producing missing values.
    """
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    result: dict = {"source_file": path.name}
    for field, pattern in FIELD_PATTERNS.items():
        match = pattern.search(text)
        if not match:
            raise ValueError(f"could not find '{field}' in {path.name}")
        raw = match.group(1)
        result[field] = raw if field == "project_id" else _parse_amount(raw)

    return result


def extract_all_pdfs(pdf_dir: Path | str = DEFAULT_PDF_DIR) -> pd.DataFrame:
    """Extract fields from every PDF in `pdf_dir` and return them as a DataFrame."""
    pdf_dir = Path(pdf_dir)
    paths = sorted(pdf_dir.glob("*.pdf"))
    if not paths:
        raise FileNotFoundError(f"no PDFs found in {pdf_dir}")

    rows = [extract_fields_from_pdf(path) for path in paths]
    df = pd.DataFrame(rows)
    cols = ["project_id", "source_file", "total_project_cost_eur", "eib_finance_eur", "cofinancing_eur"]
    return df[cols]


def main() -> None:
    """Extract fields from all sample PDFs and print the resulting table."""
    df = extract_all_pdfs()
    print(f"Extracted fields from {len(df)} PDFs in {DEFAULT_PDF_DIR}")
    print()
    print(df.to_string(index=False))

    # sanity check: EIB finance + co-financing should reconstruct total cost
    reconstructed = df["eib_finance_eur"] + df["cofinancing_eur"]
    mismatch = (reconstructed - df["total_project_cost_eur"]).abs() > 1.0
    if mismatch.any():
        print()
        print("Warning: EIB finance + co-financing does not match total cost for:")
        print(df.loc[mismatch, "project_id"].tolist())


if __name__ == "__main__":
    main()
