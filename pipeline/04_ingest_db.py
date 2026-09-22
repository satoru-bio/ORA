"""
04_ingest_db.py — Load extracted JSON records into PostgreSQL.

Dedup policy: UNIQUE (sample_id, doi) — on conflict, keep existing.
Re-run with --clear-first to replace a paper's data cleanly.

Usage:
    python pipeline/04_ingest_db.py
    python pipeline/04_ingest_db.py --doi 10.1038/s41467-022-32286-0
    python pipeline/04_ingest_db.py --clear-first
"""

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.common import (
    DEFAULT_REFERENCE_CONTEXT, EXTRACTED_DIR, all_extracted_slugs, doi_to_slug,
    get_db_conn, load_extracted,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def ingest_record(cur, r: dict) -> bool:
    """INSERT one record. Returns True if inserted, False if skipped (duplicate)."""
    src = r.get("source") or {}
    qa = r.get("qa") or {}
    an = r.get("analytical") or {}
    date_bce = r.get("date_range_bce")
    lat = r.get("site_lat")
    lon = r.get("site_long")

    point_wkt = f"SRID=4326;POINT({lon} {lat})" if lat is not None and lon is not None else None

    cur.execute("""
        INSERT INTO residue_records (
            sample_id, citation, doi, table_or_figure, extraction_route,
            provenance_of_value, original_doi, original_record_id,
            prior_graphical_report, provenance_note, reference_context,
            region, site, site_location, context,
            ceramic_type, period, date_range_from, date_range_to,
            d13C_16_0, d13C_18_0, d2H_16_0,
            author_assignment,
            extraction_method, derivatisation, instrument, lab,
            value_from, extraction_confidence, flags
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, ST_GeomFromEWKT(%s), %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (sample_id, doi) DO NOTHING
        RETURNING id
    """, (
        r["sample_id"],
        src.get("citation"),
        src.get("doi"),
        src.get("table_or_figure"),
        src.get("extraction_route"),

        r.get("provenance_of_value", "original"),
        r.get("original_doi"),
        r.get("original_record_id"),
        r.get("prior_graphical_report"),
        r.get("provenance_note"),
        r.get("reference_context", DEFAULT_REFERENCE_CONTEXT),

        r["region"],
        r["site"],
        point_wkt,
        r.get("context"),

        r.get("ceramic_type", "unknown"),
        r["period"],
        date_bce[0] if date_bce else None,
        date_bce[1] if date_bce else None,

        r["d13C_16_0"],
        r["d13C_18_0"],
        r.get("d2H_16_0"),

        r.get("author_assignment"),

        an.get("extraction_method"),
        an.get("derivatisation"),
        an.get("instrument"),
        an.get("lab"),

        qa.get("value_from", "table"),
        qa.get("extraction_confidence", "high"),
        qa.get("flags") or [],
    ))
    return cur.fetchone() is not None


def log_to_extraction_log(cur, doi: str, stage: str, tokens: int | None = None,
                          elapsed_s: float | None = None, flags: list | None = None):
    cur.execute("""
        INSERT INTO extraction_log (doi, stage, prompt_tokens, elapsed_s, flags)
        VALUES (%s, %s, %s, %s, %s)
    """, (doi, stage, tokens, elapsed_s, flags or []))


def clear_paper(conn, doi: str):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM residue_records WHERE doi = %s", (doi,))
        n = cur.rowcount
    conn.commit()
    log.info("Cleared %d records for doi=%s", n, doi)


def ingest_file(conn, slug: str, clear_first: bool = False):
    data = load_extracted(slug)
    records = data.get("records", [])
    meta = data.get("meta", {})
    doi = meta.get("doi") or (records[0]["source"]["doi"] if records else None)

    if not records:
        log.info("No records in %s, skipping", slug)
        return

    log.info("Ingesting %s: %d records (doi=%s)", slug, len(records), doi)

    if clear_first and doi:
        clear_paper(conn, doi)

    t0 = time.time()
    inserted = skipped = 0
    with conn.cursor() as cur:
        for r in records:
            try:
                if ingest_record(cur, r):
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                log.warning("  Failed row %s: %s", r.get("sample_id"), e)
                conn.rollback()

        if doi:
            log_to_extraction_log(cur, doi, "04_ingest_db",
                                  elapsed_s=time.time() - t0)
        conn.commit()

    log.info("  Inserted: %d, Skipped (dupes): %d", inserted, skipped)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doi", type=str,
                        help="Ingest only this DOI (uses doi_to_slug to find the file)")
    parser.add_argument("--clear-first", action="store_true",
                        help="Delete existing records for each DOI before inserting")
    args = parser.parse_args()

    conn = get_db_conn()

    if args.doi:
        slugs = [doi_to_slug(args.doi)]
    else:
        slugs = all_extracted_slugs()

    if not slugs:
        log.error("No extraction files found in %s", EXTRACTED_DIR)
        sys.exit(1)

    for slug in sorted(slugs):
        try:
            ingest_file(conn, slug, clear_first=args.clear_first)
        except Exception:
            log.exception("Failed to ingest %s", slug)

    conn.close()
    log.info("Done.")


if __name__ == "__main__":
    main()
