"""
01_tier_a_hammann.py — Tier A (deterministic) parse of Hammann et al. 2022 SI.

Hammann et al. 2022, Nature Communications 13:5045
"Neolithic culinary traditions revealed by cereal, milk and meat lipids in pottery
 from Scottish crannogs"
DOI: 10.1038/s41467-022-32286-0

Source: 41467_2022_32286_MOESM1_ESM.pdf (25 pages)
Data: Supplementary Table 2 (pages 20–24)
Columns extracted: Sample, δ13C16:0, δ13C18:0, Δ13C, Interpretation, Vessel type

Tier A = deterministic parse, no LLM. The PDF text extracted by pypdf is clean
enough for regex-based parsing.

Usage:
    python pipeline/01_tier_a_hammann.py [--inspect] [--si-file PATH]
"""

import argparse
import re
import sys
from pathlib import Path

import pypdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.common import (
    DATA_DIR, compute_delta, doi_to_slug, plausibility_flags,
    save_extracted, validate_records,
)

# ─── Paper metadata ───────────────────────────────────────────────────────────

CITATION  = "Hammann et al. 2022"
DOI       = "10.1038/s41467-022-32286-0"
REGION    = "Britain"
PERIOD    = "Early Neolithic"  # radiocarbon dates 3640–3350 cal BC (SI Table 1)
TABLE_REF = "Supplementary Table 2"

# Approximate WGS-84 coordinates for each crannog loch (Outer Hebrides, Scotland)
# Sources: OS grid refs from paper; converted to decimal degrees
SITE_META = {
    "LAD": {
        "name": "Loch an Duna (Ranish)",
        "lat":  58.167,
        "lon":  -6.567,
    },
    "LAR": {
        "name": "Loch Arnish",
        "lat":  58.183,
        "lon":  -6.333,
    },
    "BHO": {
        "name": "Loch Bhorgastail",
        "lat":  58.167,
        "lon":  -6.783,
    },
    "LAN": {
        "name": "Loch Langabhat",
        "lat":  58.000,
        "lon":  -6.750,
    },
}

# ─── Author interpretation normalisation ─────────────────────────────────────
# Hammann 2022 uses Δ13C < -3.5 for "pure dairy" (vs Copley 2003 threshold -3.1).
# Samples "between" the two thresholds appear as "Mixture of dairy and ruminant
# carcass fat". We store the authors' own words, normalised to schema enums.

INTERP_MAP = [
    (re.compile(r"dairy fat",           re.I), "ruminant dairy"),
    (re.compile(r"mixture of dairy",    re.I), "mixed"),
    (re.compile(r"ruminant carcass fat", re.I), "ruminant adipose"),
    (re.compile(r"non.ruminant",        re.I), "non-ruminant/porcine"),
    (re.compile(r"aquatic",             re.I), "aquatic"),
]

def normalise_interp(raw: str) -> str | None:
    for pattern, norm in INTERP_MAP:
        if pattern.search(raw):
            return norm
    return None


# ─── Vessel-type normalisation ────────────────────────────────────────────────
# Crannog vessel types are not standard ware categories; store as-is.

def clean_vessel_type(raw: str) -> str:
    # Strip page numbers, leading/trailing whitespace, collapse internal spaces
    cleaned = re.sub(r"\s*\d+\s*$", "", raw.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "unknown"


# ─── PDF parser ───────────────────────────────────────────────────────────────

# Supplementary Table 2 spans pages 20–24 (0-indexed: 19–23)
TABLE_PAGES = range(19, 25)

# Sample ID pattern: LAD/LAR/BHO/LAN + digits + hyphen + digits + optional letter
# Special: "LAR15-43 Visible Residue" is a separate entry — captured by (?:\s+Visible\s+Residue)?
SAMPLE_ID_RE = re.compile(
    r"((?:LAD|LAR|BHO|LAN)\d+-\d+[a-z0-9.]*(?:\s+Visible\s+Residue)?)"
)

# Three consecutive negative floats = d16, d18, delta (reported)
THREE_FLOATS_RE = re.compile(r"(-\d+\.\d+)\s+(-\d+\.\d+)\s+(-\d+\.\d+)")

# Single lipid-value rows: "<5" or a positive integer (lipid content) — for context only
LIPID_RE = re.compile(r"(?:<5|(\d{2,}))")


def load_pdf_text(pdf_path: Path) -> str:
    """Extract and concatenate text from Supplementary Table 2 pages."""
    reader = pypdf.PdfReader(str(pdf_path))
    parts = []
    for i in TABLE_PAGES:
        if i < len(reader.pages):
            text = reader.pages[i].extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def parse(pdf_path: Path) -> list[dict]:
    raw_text = load_pdf_text(pdf_path)

    # Find all sample IDs and their positions
    id_matches = list(SAMPLE_ID_RE.finditer(raw_text))
    if not id_matches:
        print("ERROR: no sample IDs found in text. Check PDF structure.")
        return []

    records = []
    skipped_no_data = 0
    skipped_parse_error = 0

    for i, m in enumerate(id_matches):
        sample_id = re.sub(r'\s+', ' ', m.group(1)).strip()
        # Text between this sample ID and the next
        chunk_start = m.end()
        chunk_end = id_matches[i + 1].start() if i + 1 < len(id_matches) else len(raw_text)
        chunk = raw_text[chunk_start:chunk_end]

        # Attempt to find three consecutive negative floats (d16, d18, delta_reported)
        fm = THREE_FLOATS_RE.search(chunk)
        if not fm:
            skipped_no_data += 1
            continue  # insufficient lipid / no d13C measurement

        d16   = float(fm.group(1))
        d18   = float(fm.group(2))
        delta_reported = float(fm.group(3))
        delta = compute_delta(d18, d16)

        # Sanity check: computed vs reported delta
        flags = plausibility_flags(d16, d18, delta)
        if abs(delta - delta_reported) > 0.1:
            flags.append(
                f"delta_mismatch_reported_{delta_reported}_computed_{delta}"
            )

        # Extract interpretation text (appears after the three floats)
        interp_raw = chunk[fm.end():].strip()
        # Remove "TG ", "plant sterols", "AR-", "Analysed by..." to get the interpretation
        # The interpretation ends at the first biomarker or procedural note
        interp_clean = re.split(r"(?:TG\s+C|plant sterols|AR-\d|Analysed by|Ketones)", interp_raw)[0].strip()
        interp_clean = re.sub(r"\s+", " ", interp_clean).strip()

        author_assignment = normalise_interp(interp_clean)

        # Vessel type is in the chunk before the lipid content number
        chunk_before_floats = chunk[:fm.start()]
        vessel_type = clean_vessel_type(chunk_before_floats)

        # Site from prefix
        prefix = sample_id[:3]
        site_info = SITE_META.get(prefix, {})
        site     = site_info.get("name", "unknown")
        site_lat = site_info.get("lat")
        site_lon = site_info.get("lon")

        record = {
            "sample_id": sample_id,
            "source": {
                "citation":        CITATION,
                "doi":             DOI,
                "table_or_figure": TABLE_REF,
                "extraction_route": "tierA_parse",
            },
            "region":       REGION,
            "site":         site,
            "site_lat":     site_lat,
            "site_long":    site_lon,
            "context":      None,
            "ceramic_type": vessel_type,
            "period":       PERIOD,
            "date_range_bce": [3640, 3350],
            "d13C_16_0":    d16,
            "d13C_18_0":    d18,
            "delta_13C":    delta,
            "d2H_16_0":     None,
            "author_assignment": author_assignment,
            "analytical": {
                "extraction_method": (
                    "Solvent extraction; acid-base-acid hydrolysis; "
                    "fatty acid methyl ester (FAME) derivatisation"
                ),
                "derivatisation": "BF3/methanol methylation",
                "instrument":     "GC-C-IRMS",
                "lab":            "University of Bristol / Friedrich-Alexander-Universität",
            },
            "qa": {
                "value_from":           "table",
                "extraction_confidence": "high",
                "flags": flags,
            },
        }
        records.append(record)

    print(f"  Parsed {len(records)} records with d13C data")
    print(f"  Skipped {skipped_no_data} rows (no d13C -- insufficient lipid or blank)")
    return records


# ─── Inspect mode ─────────────────────────────────────────────────────────────

def inspect(pdf_path: Path):
    print(f"\nFile: {pdf_path.name}")
    reader = pypdf.PdfReader(str(pdf_path))
    print(f"Total pages: {len(reader.pages)}")
    text = load_pdf_text(pdf_path)
    id_matches = list(SAMPLE_ID_RE.finditer(text))
    print(f"Sample IDs found: {len(id_matches)}")
    print(f"First 10: {[m.group(1) for m in id_matches[:10]]}")
    print(f"Last 10:  {[m.group(1) for m in id_matches[-10:]]}")

    # Count rows with data vs without
    with_data = 0
    without_data = 0
    for i, m in enumerate(id_matches):
        end = id_matches[i+1].start() if i+1 < len(id_matches) else len(text)
        chunk = text[m.end():end]
        if THREE_FLOATS_RE.search(chunk):
            with_data += 1
        else:
            without_data += 1
    print(f"Rows with d13C data: {with_data}")
    print(f"Rows without (low lipid / blank): {without_data}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def find_si_pdf(data_dir: Path) -> Path | None:
    for p in sorted(data_dir.iterdir()):
        if p.suffix.lower() == ".pdf" and "MOESM" in p.name:
            return p
    # Fallback: filename contains hammann or 41467
    for p in data_dir.iterdir():
        if p.suffix.lower() == ".pdf":
            n = p.name.lower()
            if "hammann" in n or "41467" in n:
                return p
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inspect", action="store_true",
                        help="Print structure summary and exit")
    parser.add_argument("--si-file", type=Path, default=None,
                        help="Path to 41467_2022_32286_MOESM1_ESM.pdf")
    args = parser.parse_args()

    si_path = args.si_file
    if si_path is None:
        si_path = find_si_pdf(DATA_DIR)
        if si_path is None:
            print(f"Could not find Hammann SI PDF in {DATA_DIR}.")
            print("Expected: 41467_2022_32286_MOESM1_ESM.pdf")
            sys.exit(1)

    if args.inspect:
        inspect(si_path)
        return

    print(f"Parsing Hammann 2022 SI: {si_path.name}")
    records = parse(si_path)

    if not records:
        print("ERROR: no records extracted.")
        sys.exit(1)

    valid, invalid = validate_records(records)
    if invalid:
        print(f"\nWARNING: {len(invalid)} records failed schema validation:")
        for r in invalid:
            print(f"  {r.get('sample_id')}: {r.get('validation_errors')}")

    slug = doi_to_slug(DOI)
    out_path = save_extracted(slug, records, meta={
        "citation":    CITATION,
        "doi":         DOI,
        "source_file": si_path.name,
        "valid":       len(valid),
        "invalid":     len(invalid),
    })
    print(f"\nSaved {len(records)} records ({len(valid)} valid, {len(invalid)} invalid)")
    print(f"  -> {out_path}")


if __name__ == "__main__":
    main()
