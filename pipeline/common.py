"""Shared utilities for the ORA extraction pipeline."""

import json
import os
import re
import sys
from pathlib import Path

import jsonschema
from dotenv import load_dotenv

load_dotenv()

# ─── Paths ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "sample_schema.json"
EXTRACTED_DIR = Path(os.getenv("ORA_EXTRACTED_DIR", ROOT / "data" / "processed" / "extracted"))
DATA_DIR = Path(os.getenv("ORA_DATA_DIR", ROOT / "data" / "raw"))

# ─── Reference thresholds (Copley et al. 2003; Evershed et al. 2008) ─────────

T_NONRUM = -1.0   # Δ¹³C > -1.0 → non-ruminant
T_DAIRY  = -3.1   # Δ¹³C < -3.1 → ruminant dairy; between → ruminant adipose

# NW-European C3 plausibility envelope
D13C_MIN, D13C_MAX  = -34.0, -22.0   # per-FA range (‰)
DELTA_MIN, DELTA_MAX = -7.0,   2.0   # Δ¹³C range (‰)

# ─── JSON Schema ──────────────────────────────────────────────────────────────

with open(SCHEMA_PATH) as _f:
    RECORD_SCHEMA = json.load(_f)

_validator = jsonschema.Draft7Validator(RECORD_SCHEMA)


def validate_record(record: dict) -> list[str]:
    """Return a list of validation error strings (empty = valid)."""
    return [str(e.message) for e in _validator.iter_errors(record)]


def validate_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split records into (valid, invalid). Invalid records carry a 'validation_errors' key."""
    valid, invalid = [], []
    for r in records:
        errs = validate_record(r)
        if errs:
            r = {**r, "validation_errors": errs}
            invalid.append(r)
        else:
            valid.append(r)
    return valid, invalid


# ─── δ¹³C helpers ─────────────────────────────────────────────────────────────

def compute_delta(d13C_18_0: float, d13C_16_0: float) -> float:
    return round(d13C_18_0 - d13C_16_0, 2)


def band_of(delta: float) -> str:
    if delta > T_NONRUM:
        return "non-ruminant/porcine"
    if delta < T_DAIRY:
        return "ruminant dairy"
    return "ruminant adipose"


def plausibility_flags(d16: float, d18: float, delta: float) -> list[str]:
    flags = []
    if not (D13C_MIN <= d16 <= D13C_MAX):
        flags.append("d16_out_of_C3_range")
    if not (D13C_MIN <= d18 <= D13C_MAX):
        flags.append("d18_out_of_C3_range")
    if not (DELTA_MIN <= delta <= DELTA_MAX):
        flags.append("delta_out_of_range")
    return flags


# ─── Author-agreement check ───────────────────────────────────────────────────

# Maps standard author_assignment strings to their expected Δ¹³C bands
ASSIGNMENT_TO_BAND = {
    "ruminant dairy":     "ruminant dairy",
    "ruminant adipose":   "ruminant adipose",
    "non-ruminant/porcine": "non-ruminant/porcine",
    # aquatic / mixed / none are not straightforwardly mappable to a single band
}


def author_agrees(author_assignment: str | None, delta: float) -> bool | None:
    """
    True if the computed Δ¹³C band matches the author's assignment.
    None if the assignment is not mappable (aquatic, mixed, none, null).
    """
    if not author_assignment or author_assignment not in ASSIGNMENT_TO_BAND:
        return None
    expected_band = ASSIGNMENT_TO_BAND[author_assignment]
    return band_of(delta) == expected_band


# ─── JSON I/O ─────────────────────────────────────────────────────────────────

def save_extracted(doi_slug: str, records: list[dict], meta: dict | None = None) -> Path:
    """Save extracted records to data/processed/extracted/<doi_slug>.json."""
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out = {"meta": meta or {}, "records": records}
    path = EXTRACTED_DIR / f"{doi_slug}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    return path


def load_extracted(doi_slug: str) -> dict:
    path = EXTRACTED_DIR / f"{doi_slug}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def all_extracted_slugs() -> list[str]:
    return [p.stem for p in EXTRACTED_DIR.glob("*.json")]


# ─── PDF text extraction ──────────────────────────────────────────────────────

def extract_pdf_text(pdf_path: Path, page_limit: int = 80) -> str:
    """Extract text from a PDF using pypdf. Returns concatenated page text."""
    try:
        import pypdf
    except ImportError:
        sys.exit("pypdf not installed — run: pip install pypdf")

    reader = pypdf.PdfReader(str(pdf_path))
    pages = reader.pages[:page_limit]
    parts = []
    for i, page in enumerate(pages):
        text = page.extract_text() or ""
        parts.append(f"[PAGE {i+1}]\n{text}")
    return "\n\n".join(parts)


# ─── DB connection ─────────────────────────────────────────────────────────────

def get_db_conn():
    try:
        import psycopg2
    except ImportError:
        sys.exit("psycopg2 not installed — run: pip install psycopg2-binary")

    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set — copy .env.example to .env and configure it")
    return psycopg2.connect(url)


# ─── Slug helper ──────────────────────────────────────────────────────────────

def doi_to_slug(doi: str) -> str:
    """Convert a DOI to a filesystem-safe slug."""
    return re.sub(r"[^\w\-]", "_", doi)
