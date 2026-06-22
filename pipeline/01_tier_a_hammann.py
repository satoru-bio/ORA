"""
01_tier_a_hammann.py — Tier A (deterministic) parse of Hammann et al. 2022 SI.

Hammann et al. 2022, Nature Communications 13:5045
"Earliest pottery use in the British Neolithic linked to keeping and processing
 of domesticated animals"
DOI: 10.1038/s41467-022-32286-0

This script reads the deposited supplementary spreadsheet directly — no LLM.
Run inspect mode first to identify the correct sheet and column names:

    python pipeline/01_tier_a_hammann.py --inspect

Then run the full parse:

    python pipeline/01_tier_a_hammann.py

The SI spreadsheet must be placed in ORA_DATA_DIR (default: data/raw/).
Look for a file whose name contains "41467" or "hammann" or "supplementary_data".
"""

import argparse
import json
import sys
from pathlib import Path

import openpyxl

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.common import (
    DATA_DIR, compute_delta, doi_to_slug, plausibility_flags,
    save_extracted, validate_records,
)

# ─── Paper metadata ───────────────────────────────────────────────────────────

CITATION = "Hammann et al. 2022"
DOI      = "10.1038/s41467-022-32286-0"
REGION   = "Britain"   # all sites are in Scotland

# ─── Expected column names (try these in order; edit if the SI uses different names) ─

# Candidates for each field — matched case-insensitively, partial match ok
COLUMN_CANDIDATES = {
    "sample_id":        ["sherd", "sample id", "sample_id", "vessel", "pot no", "pot number"],
    "site":             ["site", "site name", "location"],
    "ceramic_type":     ["ware", "pottery type", "ceramic type", "vessel type"],
    "period":           ["period", "phase", "chronological"],
    "d13C_16_0":        ["δ13c c16", "d13c c16", "δ13c16", "d13c16", "δ13c 16:0",
                         "d13c 16:0", "d13c_c16", "δ13c(c16:0)", "c16:0 δ13c"],
    "d13C_18_0":        ["δ13c c18", "d13c c18", "δ13c18", "d13c18", "δ13c 18:0",
                         "d13c 18:0", "d13c_c18", "δ13c(c18:0)", "c18:0 δ13c"],
    "delta_13C":        ["δ13c", "delta13c", "Δ13c", "Δδ13c"],
    "d2H_16_0":         ["δ2h", "d2h", "δdh", "δ2h c16", "dh c16"],
    "author_assignment": ["assignment", "commodity", "origin", "interpretation",
                          "lipid class", "fat type"],
    "site_lat":         ["latitude", "lat"],
    "site_long":        ["longitude", "lon", "long"],
    "context":          ["context", "feature", "layer"],
    "date_range_from":  ["date from", "cal bc from", "start date", "from bc"],
    "date_range_to":    ["date to", "cal bc to", "end date", "to bc"],
}

# Period normalisation mapping (handle various paper conventions)
PERIOD_MAP = {
    "en": "Early Neolithic",
    "early neolithic": "Early Neolithic",
    "mn": "Middle Neolithic",
    "middle neolithic": "Middle Neolithic",
    "ln": "Late Neolithic",
    "late neolithic": "Late Neolithic",
    "neolithic": "Neolithic (unspec)",
    "neo": "Neolithic (unspec)",
}

# Author assignment normalisation
ASSIGNMENT_MAP = {
    "dairy": "ruminant dairy",
    "ruminant dairy": "ruminant dairy",
    "adipose": "ruminant adipose",
    "ruminant adipose": "ruminant adipose",
    "non-ruminant": "non-ruminant/porcine",
    "porcine": "non-ruminant/porcine",
    "non-ruminant/porcine": "non-ruminant/porcine",
    "aquatic": "aquatic",
    "marine": "aquatic",
    "mixed": "mixed",
    "none": "none",
}


def find_si_file(data_dir: Path) -> Path | None:
    """Search data_dir for a file that looks like the Hammann 2022 SI."""
    keywords = ["41467", "hammann", "supplementary_data", "supplementary data",
                "s1", "sd1", "supp"]
    for p in data_dir.iterdir():
        if p.suffix.lower() in (".xlsx", ".xls", ".ods", ".csv"):
            name_lower = p.name.lower()
            if any(kw in name_lower for kw in keywords):
                return p
    # Fallback: return the first spreadsheet in the directory
    for p in data_dir.iterdir():
        if p.suffix.lower() in (".xlsx", ".xls"):
            return p
    return None


def match_column(header: str, candidates: list[str]) -> bool:
    h = header.lower().strip()
    return any(c in h or h in c for c in candidates)


def find_columns(ws) -> dict[str, int]:
    """
    Read the first row of ws and return a mapping {field_name: col_index_0based}.
    Prints all headers so the user can inspect / adjust COLUMN_CANDIDATES above.
    """
    headers = []
    for cell in ws[1]:
        headers.append(str(cell.value or "").strip())

    print(f"  Sheet '{ws.title}' headers: {headers}")

    col_map = {}
    for field, candidates in COLUMN_CANDIDATES.items():
        for i, h in enumerate(headers):
            if match_column(h, candidates):
                col_map[field] = i
                break

    return col_map


def normalise_period(raw: str | None) -> str:
    if not raw:
        return "Neolithic (unspec)"
    key = str(raw).strip().lower()
    return PERIOD_MAP.get(key, "Neolithic (unspec)")


def normalise_assignment(raw: str | None) -> str | None:
    if not raw:
        return None
    key = str(raw).strip().lower()
    return ASSIGNMENT_MAP.get(key, None)


def parse_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ─── Main parse ───────────────────────────────────────────────────────────────

def parse_sheet(ws, col_map: dict[str, int]) -> list[dict]:
    records = []
    skipped = 0

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        def get(field):
            idx = col_map.get(field)
            return row[idx] if idx is not None and idx < len(row) else None

        sample_id_raw = get("sample_id")
        if sample_id_raw is None:
            continue   # blank row

        d16 = parse_float(get("d13C_16_0"))
        d18 = parse_float(get("d13C_18_0"))

        if d16 is None or d18 is None:
            skipped += 1
            print(f"  Row {row_idx}: skipping — missing d13C values "
                  f"(d16={get('d13C_16_0')!r}, d18={get('d13C_18_0')!r})")
            continue

        delta_raw = parse_float(get("delta_13C"))
        delta = compute_delta(d18, d16)
        if delta_raw is not None and abs(delta - delta_raw) > 0.05:
            print(f"  Row {row_idx}: computed Δ¹³C {delta:.2f} differs from reported "
                  f"{delta_raw:.2f} — using computed value")

        flags = plausibility_flags(d16, d18, delta)

        d2h = parse_float(get("d2H_16_0"))
        date_from = parse_int(get("date_range_from"))
        date_to   = parse_int(get("date_range_to"))

        record = {
            "sample_id": str(sample_id_raw).strip(),
            "source": {
                "citation":        CITATION,
                "doi":             DOI,
                "table_or_figure": f"Supplementary Data — sheet '{ws.title}'",
                "extraction_route": "tierA_parse",
            },
            "region":       REGION,
            "site":         str(get("site") or "unknown").strip(),
            "site_lat":     parse_float(get("site_lat")),
            "site_long":    parse_float(get("site_long")),
            "context":      str(get("context")).strip() if get("context") else None,
            "ceramic_type": str(get("ceramic_type") or "unknown").strip(),
            "period":       normalise_period(get("period")),
            "date_range_bce": [date_from, date_to] if date_from and date_to else None,
            "d13C_16_0":    d16,
            "d13C_18_0":    d18,
            "delta_13C":    delta,
            "d2H_16_0":     d2h,
            "author_assignment": normalise_assignment(get("author_assignment")),
            "analytical": {
                "extraction_method": "solvent / acidified-methanol direct (Correa-Ascencio & Evershed 2014)",
                "derivatisation":    "methylation",
                "instrument":        "GC-C-IRMS",
                "lab":               None,
            },
            "qa": {
                "value_from":           "table",
                "extraction_confidence": "high",
                "flags": flags,
            },
        }
        records.append(record)

    print(f"  Parsed {len(records)} records, skipped {skipped} rows (missing δ¹³C).")
    return records


def inspect(si_path: Path):
    """Print all sheets and columns so the user can configure COLUMN_CANDIDATES."""
    wb = openpyxl.load_workbook(si_path, read_only=True, data_only=True)
    print(f"\nWorkbook: {si_path.name}")
    print(f"Sheets: {wb.sheetnames}\n")
    for name in wb.sheetnames:
        ws = wb[name]
        find_columns(ws)
    wb.close()


def run(si_path: Path, sheet_name: str | None = None):
    print(f"Parsing: {si_path.name}")
    wb = openpyxl.load_workbook(si_path, read_only=True, data_only=True)

    if sheet_name:
        sheets = [wb[sheet_name]]
    else:
        # Parse all sheets; skip any that don't have both d13C columns
        sheets = [wb[n] for n in wb.sheetnames]

    all_records = []
    for ws in sheets:
        col_map = find_columns(ws)
        if "d13C_16_0" not in col_map or "d13C_18_0" not in col_map:
            print(f"  Sheet '{ws.title}': no δ¹³C columns found, skipping.")
            continue
        records = parse_sheet(ws, col_map)
        all_records.extend(records)

    wb.close()

    if not all_records:
        print("ERROR: no records extracted. Run with --inspect to check column names.")
        sys.exit(1)

    valid, invalid = validate_records(all_records)
    if invalid:
        print(f"\nWARNING: {len(invalid)} records failed schema validation:")
        for r in invalid:
            print(f"  {r['sample_id']}: {r['validation_errors']}")

    slug = doi_to_slug(DOI)
    out_path = save_extracted(slug, all_records, meta={
        "citation": CITATION,
        "doi": DOI,
        "source_file": si_path.name,
        "valid": len(valid),
        "invalid": len(invalid),
    })
    print(f"\nSaved {len(all_records)} records ({len(valid)} valid, {len(invalid)} invalid)"
          f"\n  → {out_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inspect", action="store_true",
                        help="Print all sheet names and column headers, then exit")
    parser.add_argument("--si-file", type=Path, default=None,
                        help="Path to the Hammann 2022 SI spreadsheet. "
                             "If omitted, searched in ORA_DATA_DIR.")
    parser.add_argument("--sheet", type=str, default=None,
                        help="Parse only this sheet (default: all sheets)")
    args = parser.parse_args()

    si_path = args.si_file
    if si_path is None:
        si_path = find_si_file(DATA_DIR)
        if si_path is None:
            print(f"Could not find Hammann 2022 SI spreadsheet in {DATA_DIR}.\n"
                  f"Download it from: https://doi.org/10.1038/s41467-022-32286-0\n"
                  f"(Supplementary Data file) and place it in ORA_DATA_DIR.\n"
                  f"Then re-run: python pipeline/01_tier_a_hammann.py --inspect")
            sys.exit(1)

    if args.inspect:
        inspect(si_path)
        return

    run(si_path, sheet_name=args.sheet)


if __name__ == "__main__":
    main()
