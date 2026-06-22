"""
05_export.py — Export the corpus as JSON and CSV.

Outputs:
  - frontend/public/corpus.json   (consumed by the web tool)
  - data/exports/corpus.csv       (for download + archiving)
  - data/exports/corpus.json      (full schema, CC-BY licensed)

Generates from the PostgreSQL DB (requires 04_ingest_db.py to have run).
For a quick rebuild without Docker, pass --from-extracted to read the
JSON intermediates directly instead of querying the DB.

Usage:
    python pipeline/05_export.py
    python pipeline/05_export.py --from-extracted
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.common import EXTRACTED_DIR, ROOT, all_extracted_slugs, get_db_conn, load_extracted

EXPORT_DIR = ROOT / "data" / "exports"
FRONTEND_PUBLIC = ROOT / "frontend" / "public"

EXPORT_META = {
    "title": "ORA — Organic Residue Archive: British and Irish Neolithic pottery δ¹³C",
    "version": "1.0",
    "license": "CC-BY 4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "cite_as": (
        "Satoru / DigiShield Labs (2025). ORA: Organic Residue Archive — "
        "compound-specific δ¹³C from British and Irish Neolithic pottery lipid residue studies. "
        "CC-BY 4.0. github.com/satoru-bio/ORA"
    ),
    "cite_original_studies": (
        "Per-record source attribution is mandatory. Cite the original study "
        "listed in each record's source.citation field alongside this dataset."
    ),
    "description": (
        "Harmonised, value-level dataset of compound-specific δ¹³C "
        "(C16:0 and C18:0 fatty acids) extracted from published British and Irish "
        "Neolithic pottery lipid residue studies. Δ¹³C = δ¹³C18:0 − δ¹³C16:0. "
        "Reference thresholds after Copley et al. 2003 and Evershed et al. 2008 "
        "(NW-European C3 context). This dataset is for contextualisation only — "
        "it does not classify unknown samples."
    ),
    "aquatic_caveat": (
        "Δ¹³C alone cannot resolve aquatic/marine fats from non-ruminant adipose — "
        "they overlap. Separating them requires biomarker evidence "
        "(isoprenoid acids, C20/C22 APAAs) not captured in this dataset."
    ),
}

# Columns written to CSV (flat subset of the full schema)
CSV_COLUMNS = [
    "sample_id", "citation", "doi", "table_or_figure", "extraction_route",
    "region", "site", "site_lat", "site_long",
    "ceramic_type", "period", "date_range_from", "date_range_to",
    "d13C_16_0", "d13C_18_0", "delta_13C", "d2H_16_0",
    "author_assignment",
    "extraction_method", "derivatisation", "instrument", "lab",
    "value_from", "extraction_confidence", "flags",
]


# ─── DB export ────────────────────────────────────────────────────────────────

DB_QUERY = """
SELECT
    r.sample_id,
    r.citation,
    r.doi,
    r.table_or_figure,
    r.extraction_route,
    r.region,
    r.site,
    ST_Y(r.site_location) AS site_lat,
    ST_X(r.site_location) AS site_long,
    r.context,
    r.ceramic_type,
    r.period,
    r.date_range_from,
    r.date_range_to,
    r.d13C_16_0,
    r.d13C_18_0,
    r.delta_13C,
    r.d2H_16_0,
    r.author_assignment,
    r.extraction_method,
    r.derivatisation,
    r.instrument,
    r.lab,
    r.value_from,
    r.extraction_confidence,
    r.flags
FROM residue_records r
ORDER BY r.citation, r.site, r.sample_id
"""


def records_from_db() -> list[dict]:
    conn = get_db_conn()
    with conn.cursor() as cur:
        cur.execute(DB_QUERY)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
    conn.close()
    records = []
    for row in rows:
        r = dict(zip(cols, row))
        r["flags"] = list(r["flags"]) if r["flags"] else []
        # Reconstruct nested source / analytical / qa objects
        rec = _flatten_to_full(r)
        records.append(rec)
    return records


def _flatten_to_full(r: dict) -> dict:
    """Reconstruct the full JSON schema shape from a flat DB row."""
    date_from = r.get("date_range_from")
    date_to = r.get("date_range_to")
    return {
        "sample_id": r["sample_id"],
        "source": {
            "citation":        r["citation"],
            "doi":             r["doi"],
            "table_or_figure": r["table_or_figure"],
            "extraction_route": r["extraction_route"],
        },
        "region":       r["region"],
        "site":         r["site"],
        "site_lat":     float(r["site_lat"]) if r.get("site_lat") is not None else None,
        "site_long":    float(r["site_long"]) if r.get("site_long") is not None else None,
        "context":      r.get("context"),
        "ceramic_type": r.get("ceramic_type", "unknown"),
        "period":       r["period"],
        "date_range_bce": [date_from, date_to] if date_from and date_to else None,
        "d13C_16_0":    float(r["d13C_16_0"]),
        "d13C_18_0":    float(r["d13C_18_0"]),
        "delta_13C":    float(r["delta_13C"]),
        "d2H_16_0":     float(r["d2H_16_0"]) if r.get("d2H_16_0") is not None else None,
        "author_assignment": r.get("author_assignment"),
        "analytical": {
            "extraction_method": r.get("extraction_method"),
            "derivatisation":    r.get("derivatisation"),
            "instrument":        r.get("instrument"),
            "lab":               r.get("lab"),
        },
        "qa": {
            "value_from":           r.get("value_from", "table"),
            "extraction_confidence": r.get("extraction_confidence", "high"),
            "flags":               r.get("flags", []),
        },
    }


# ─── Extracted-JSON export (no DB) ────────────────────────────────────────────

def records_from_extracted() -> list[dict]:
    records = []
    for slug in sorted(all_extracted_slugs()):
        data = load_extracted(slug)
        records.extend(data.get("records", []))
    return records


# ─── Flat row for CSV ─────────────────────────────────────────────────────────

def to_csv_row(r: dict) -> dict:
    src = r.get("source") or {}
    an = r.get("analytical") or {}
    qa = r.get("qa") or {}
    date_bce = r.get("date_range_bce")
    return {
        "sample_id":         r["sample_id"],
        "citation":          src.get("citation"),
        "doi":               src.get("doi"),
        "table_or_figure":   src.get("table_or_figure"),
        "extraction_route":  src.get("extraction_route"),
        "region":            r["region"],
        "site":              r["site"],
        "site_lat":          r.get("site_lat"),
        "site_long":         r.get("site_long"),
        "ceramic_type":      r.get("ceramic_type", "unknown"),
        "period":            r["period"],
        "date_range_from":   date_bce[0] if date_bce else None,
        "date_range_to":     date_bce[1] if date_bce else None,
        "d13C_16_0":         r["d13C_16_0"],
        "d13C_18_0":         r["d13C_18_0"],
        "delta_13C":         r["delta_13C"],
        "d2H_16_0":          r.get("d2H_16_0"),
        "author_assignment": r.get("author_assignment"),
        "extraction_method": an.get("extraction_method"),
        "derivatisation":    an.get("derivatisation"),
        "instrument":        an.get("instrument"),
        "lab":               an.get("lab"),
        "value_from":        qa.get("value_from"),
        "extraction_confidence": qa.get("extraction_confidence"),
        "flags":             "|".join(qa.get("flags") or []),
    }


# ─── Frontend corpus shape ────────────────────────────────────────────────────

def to_frontend_record(r: dict) -> dict:
    """Minimal shape for the web tool. Keeps provenance for hover tooltips."""
    src = r.get("source") or {}
    return {
        "id":           r["sample_id"],
        "d16":          r["d13C_16_0"],
        "d18":          r["d13C_18_0"],
        "delta":        r["delta_13C"],
        "site":         r["site"],
        "region":       r["region"],
        "period":       r.get("period", "Neolithic (unspec)"),
        "ceramic_type": r.get("ceramic_type", "unknown"),
        "citation":     src.get("citation", ""),
        "doi":          src.get("doi", ""),
        "table_fig":    src.get("table_or_figure", ""),
        "author_assignment": r.get("author_assignment"),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-extracted", action="store_true",
                        help="Read JSON intermediates instead of querying the DB")
    args = parser.parse_args()

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)

    print("Loading records ...")
    if args.from_extracted:
        records = records_from_extracted()
        print(f"  {len(records)} records from extracted JSONs")
    else:
        records = records_from_db()
        print(f"  {len(records)} records from DB")

    if not records:
        print("ERROR: no records to export.")
        sys.exit(1)

    sources = sorted(set((r.get("source") or {}).get("citation", "") for r in records))
    now = datetime.now(timezone.utc).isoformat()

    # ── Full JSON (archival) ──────────────────────────────────────────────────
    full_json = {
        "meta": {**EXPORT_META, "generated": now, "record_count": len(records), "sources": sources},
        "records": records,
    }
    full_path = EXPORT_DIR / "corpus.json"
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(full_json, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {full_path} ({len(records)} records)")

    # ── CSV ───────────────────────────────────────────────────────────────────
    csv_path = EXPORT_DIR / "corpus.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in records:
            writer.writerow(to_csv_row(r))
    print(f"  Wrote {csv_path}")

    # ── Frontend corpus.json ──────────────────────────────────────────────────
    frontend_records = [to_frontend_record(r) for r in records]
    frontend_json = {
        "meta": {
            "generated": now,
            "record_count": len(frontend_records),
            "sources": sources,
            "license": "CC-BY 4.0 — cite Satoru/DigiShield Labs + original studies",
            "aquatic_caveat": EXPORT_META["aquatic_caveat"],
        },
        "records": frontend_records,
    }
    frontend_path = FRONTEND_PUBLIC / "corpus.json"
    with open(frontend_path, "w", encoding="utf-8") as f:
        json.dump(frontend_json, f, ensure_ascii=False)  # compact for browser
    print(f"  Wrote {frontend_path} (frontend corpus)")

    print(f"\nDone. {len(records)} records, {len(sources)} sources.")
    print("Next: cd frontend && npm install && npm run dev")


if __name__ == "__main__":
    main()
