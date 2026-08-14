"""
02_tier_b_extract.py — LLM-assisted extraction (Tier B) for PDF-based papers.

The corpus is SIX papers (see pipeline/seed_corpus.py for canonical DOIs).
Hammann et al. 2022 is handled by Tier A (01_tier_a_hammann.py); the five
remaining papers are extracted here via LLM.

Tier B papers (SEED_DOIS minus Tier A):
  1. Copley et al. 2005 (III), JAS 32:523–546    DOI 10.1016/j.jas.2004.08.006
  2. Cramp et al. 2014, Proc R Soc B 281:20132372 DOI 10.1098/rspb.2013.2372
  3. Smyth & Evershed 2016, Environ Archaeol 21  DOI 10.1179/1749631414Y.0000000045

  Two papers removed from active corpus (2026-08-14) — per-sherd values only in
  scatter-plot figures (Tier C), no SI found:
    Copley et al. 2003 (PNAS 100:1524–29)     DOI 10.1073/pnas.0335955100
    Mukherjee et al. 2008 (JAS 35:2059–73)    DOI 10.1016/j.jas.2008.01.010
  See EXCLUDED_DOIS in seed_corpus.py for full notes.

Usage (extract one paper):
    python pipeline/02_tier_b_extract.py --doi 10.1016/j.jas.2004.08.006

Usage (extract all Tier B papers):
    python pipeline/02_tier_b_extract.py --all

--all iterates SEED_DOIS (from seed_corpus.py) and skips any DOI not in the
Tier B CORPUS dict (i.e. Hammann, which is Tier A).

Costs are logged per paper. Expected total: well under $5 for the five Tier B papers.
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.common import (
    DATA_DIR, compute_delta, doi_to_slug, extract_pdf_text,
    plausibility_flags, save_extracted, validate_records,
)
from pipeline.seed_corpus import EXCLUDED_DOIS, SEED_CORPUS, SEED_DOIS

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Corpus configuration ─────────────────────────────────────────────────────
# CORPUS is built at module load — never edit citation or raw_deposit here.
#
# Two sources:
#   seed_corpus.SEED_CORPUS — canonical paper metadata (citation/ref, raw_deposit).
#   _TIER_B_OPERATIONAL     — Tier-B-only extraction config (pdf_hint, table hints,
#                             region default, notes). Edit these here.
#
# Assertion: every key in _TIER_B_OPERATIONAL must be in SEED_DOIS.

_SEED_BY_DOI: dict = {c["doi"]: c for c in SEED_CORPUS}

_TIER_B_OPERATIONAL: dict = {
    "10.1016/j.jas.2004.08.006": {
        "pdf_hint":          "S0305440304001189",
        "table_or_figure":   "Table 2",
        "region_default":    "Britain",
        "filter_neolithic":  False,
        "notes": "438 sherds, 6 sites, southern Britain Neolithic.",
    },
    "10.1098/rspb.2013.2372": {
        "pdf_hint":          "rspb.2013.2372",
        "table_or_figure":   "Table 1 / Electronic Supplementary Material",
        "region_default":    None,   # mixed Britain + Ireland — tag per row
        "filter_neolithic":  False,
        "notes": (
            "Mixed British and Irish samples — tag region per row. "
            "Concerns fishing-to-dairying transition; aquatic samples present. "
            "Aquatic caveat applies: delta-13C alone cannot resolve aquatic/marine fats."
        ),
    },
    "10.1179/1749631414Y.0000000045": {
        "pdf_hint":          "SmythEvershed",
        "table_or_figure":   "Table 1 / Appendix",
        "region_default":    "Ireland",
        "filter_neolithic":  False,
        "notes": "~450 vessels, 15 Irish sites.",
    },
}

_missing_from_seed = set(_TIER_B_OPERATIONAL) - set(SEED_DOIS)
assert not _missing_from_seed, (
    f"_TIER_B_OPERATIONAL DOI(s) not in SEED_DOIS: {_missing_from_seed}"
)


def _build_corpus() -> dict:
    """Merge SEED_CORPUS metadata with Tier-B operational config.

    citation derives from SEED_CORPUS ref; raw_deposit (if present on the
    seed entry) is condensed and carried through to the JSON intermediate
    meta block. Neither field should be set directly in _TIER_B_OPERATIONAL.
    """
    out = {}
    for doi, ops in _TIER_B_OPERATIONAL.items():
        seed = _SEED_BY_DOI[doi]
        entry: dict = {"citation": seed["ref"], **ops}
        if seed.get("raw_deposit"):
            rd = seed["raw_deposit"]
            # Condense: everything before the "Candidate source" clause.
            condensed = rd["note"].split(". Candidate")[0].rstrip(".")
            entry["raw_deposit"] = {
                "doi":   rd["doi"],
                "url":   rd["url"],
                "title": rd["title"],
                "note":  condensed,
            }
        out[doi] = entry
    return out


CORPUS = _build_corpus()

# ─── Model split ─────────────────────────────────────────────────────────────

MODEL_TRIAGE  = "claude-haiku-4-5-20251001"
MODEL_EXTRACT = "claude-sonnet-4-6"

# ─── Prompts ──────────────────────────────────────────────────────────────────

TRIAGE_SYSTEM = """\
You are a research assistant reading archaeological chemistry papers.
Your task: identify which tables and figures in this paper contain
compound-specific stable isotope data (δ¹³C or δ²H values for individual
C16:0 and C18:0 fatty acids from pottery residues).

Respond with a JSON object:
{
  "has_compound_specific_data": true | false,
  "tables_with_d13C": ["Table 1", "Table 2", ...],
  "figures_with_d13C": ["Figure 3", ...],
  "notes": "any relevant observations"
}

Only tables are eligible for Tier B extraction; figures are excluded.
"""

EXTRACT_SYSTEM = """\
You are a data extractor for an archaeological chemistry dataset.
Extract compound-specific δ¹³C values from pottery lipid residue tables.

Schema for each record:
{
  "sample_id": "the paper's own sherd/vessel label",
  "site": "site name as given in the paper",
  "region": "Britain" | "Ireland",
  "context": "context or feature label if given, otherwise null",
  "ceramic_type": "ware type if stated (Grooved Ware, Peterborough Ware, etc.), otherwise 'unknown'",
  "period": "Early Neolithic" | "Middle Neolithic" | "Late Neolithic" | "Neolithic (unspec)",
  "date_range_bce": [from_integer, to_integer] | null,
  "d13C_16_0": number (δ¹³C of C16:0, per mille),
  "d13C_18_0": number (δ¹³C of C18:0, per mille),
  "delta_13C": number (= d13C_18_0 - d13C_16_0; compute if not given explicitly),
  "d2H_16_0": number | null,
  "author_assignment": "ruminant dairy" | "ruminant adipose" | "non-ruminant/porcine" | "aquatic" | "mixed" | "none" | null,
  "value_from": "table",
  "table_or_figure": "e.g. Table 2",
  "extraction_confidence": "high" | "medium" | "low"
}

Critical rules:
1. Extract EVERY row that has both δ¹³C16:0 AND δ¹³C18:0 values.
2. Compute delta_13C = d13C_18_0 - d13C_16_0. Never leave it null.
3. Record author_assignment EXACTLY as stated in the paper — normalise only to:
   "ruminant dairy", "ruminant adipose", "non-ruminant/porcine", "aquatic", "mixed", "none".
   If the paper uses different words, pick the closest. If none applies, use null.
4. Values only from named tables. Do NOT estimate values from scatter plots or figures.
5. If a value is illegible or absent, omit that row.
6. Tag period per row. If the paper has a consistent period for all sherds, apply it to every row.
7. Tag region per row: Britain (England, Scotland, Wales) or Ireland.
8. Output format: return COMPACT JSON — no pretty-printing, no extra whitespace between elements.
   One record per line is ideal. This is critical to stay within the output token budget.
   If the text you are given is only a portion of the full PDF, extract only complete rows
   visible in this portion; do not invent or infer missing rows.

Return a compact JSON array (may be empty if no eligible rows found).
"""

EXTRACT_USER_TEMPLATE = """\
Paper: {citation}
DOI: {doi}
Notes: {notes}
Target tables: {target_tables}

PDF text (may contain multiple tables; extract from the named tables only):
---
{pdf_text}
---

Return a JSON array of records as described. No commentary outside the JSON array.
"""


# ─── Helper: find PDF ─────────────────────────────────────────────────────────

def find_pdf(hint: str, data_dir: Path) -> Path | None:
    hint_lower = hint.lower()
    for p in data_dir.iterdir():
        if p.suffix.lower() == ".pdf" and hint_lower in p.name.lower():
            return p
    return None


# ─── Extraction pipeline (per paper) ──────────────────────────────────────────

def triage(client: anthropic.Anthropic, pdf_text: str) -> dict:
    """Stage 1 (Haiku): identify which tables contain δ¹³C data."""
    msg = client.messages.create(
        model=MODEL_TRIAGE,
        max_tokens=512,
        system=TRIAGE_SYSTEM,
        messages=[{"role": "user", "content": pdf_text[:80_000]}],
    )
    raw = msg.content[0].text
    tokens = msg.usage.input_tokens + msg.usage.output_tokens
    # strip markdown fence if present
    raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
    try:
        return json.loads(raw), tokens
    except json.JSONDecodeError:
        return {"has_compound_specific_data": False, "tables_with_d13C": [],
                "figures_with_d13C": [], "notes": f"triage parse error: {raw}"}, tokens


def _extract_single_chunk(
    client: anthropic.Anthropic,
    pdf_chunk: str,
    doi: str,
    config: dict,
    target_tables: list[str],
) -> tuple[list[dict] | None, int, str]:
    """Call Sonnet on one chunk of PDF text.

    Returns (records_or_None, tokens_used, stop_reason).
    records_or_None is None on JSON parse failure; caller should treat as empty.
    stop_reason is 'end_turn' on clean finish, 'max_tokens' if truncated.
    """
    user_msg = EXTRACT_USER_TEMPLATE.format(
        citation=config["citation"],
        doi=doi,
        notes=config.get("notes", ""),
        target_tables=", ".join(target_tables) or config["table_or_figure"],
        pdf_text=pdf_chunk,
    )
    msg = client.messages.create(
        model=MODEL_EXTRACT,
        max_tokens=16384,
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = msg.content[0].text.strip()
    tokens = msg.usage.input_tokens + msg.usage.output_tokens
    stop_reason = msg.stop_reason
    raw = re.sub(r"```json\s*|\s*```", "", raw).strip()
    try:
        records = json.loads(raw)
        if not isinstance(records, list):
            records = [records]
        return records, tokens, stop_reason
    except json.JSONDecodeError as e:
        # If raw doesn't look like JSON the model returned prose ("no data in this chunk")
        # rather than a malformed array — log at WARNING, not ERROR.
        is_prose = raw and not raw.lstrip().startswith(("[", "{"))
        if is_prose:
            log.warning("Chunk returned prose instead of JSON (no table rows in this portion): %s...",
                        raw[:120])
        else:
            log.error("JSON parse error on Sonnet output (stop=%s): %s\nRaw (first 400): %s",
                      stop_reason, e, raw[:400])
        return None, tokens, stop_reason


def extract_records(
    client: anthropic.Anthropic,
    pdf_text: str,
    doi: str,
    config: dict,
    target_tables: list[str],
) -> tuple[list[dict], int]:
    """Stage 2 (Sonnet): extract all δ¹³C rows from the identified tables.

    For PDFs ≤ CHUNK_THRESHOLD chars, uses a single API call.
    For larger PDFs, splits into overlapping chunks and merges results by sample_id.
    Chunking keeps each call's output well under the 16384 max_tokens limit.
    """
    CHUNK_THRESHOLD = 30_000  # chars; single-pass below this, chunked above
    CHUNK_SIZE      = 15_000  # chars per chunk
    CHUNK_OVERLAP   =    500  # trailing chars repeated in next chunk (avoids split rows)
    MAX_TEXT        = 120_000 # hard cap on total PDF chars consumed

    text = pdf_text[:MAX_TEXT]

    if len(text) <= CHUNK_THRESHOLD:
        records, tokens, stop_reason = _extract_single_chunk(
            client, text, doi, config, target_tables,
        )
        if stop_reason == "max_tokens":
            log.warning("Short-PDF extraction truncated (stop=max_tokens); some records may be missing.")
        return (records or []), tokens

    # ── Chunked path for long PDFs ───────────────────────────────────────────
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end])
        next_start = start + CHUNK_SIZE - CHUNK_OVERLAP
        if next_start <= start:
            break
        start = next_start

    log.info("Long PDF (%d chars) -> chunked extraction: %d chunks of ~%d chars",
             len(text), len(chunks), CHUNK_SIZE)

    all_records: list[dict] = []
    total_tokens = 0
    seen_ids: set[str] = set()

    for i, chunk in enumerate(chunks):
        log.info("  Chunk %d/%d (%d chars)...", i + 1, len(chunks), len(chunk))
        recs, tok, stop_reason = _extract_single_chunk(
            client, chunk, doi, config, target_tables,
        )
        total_tokens += tok
        if stop_reason == "max_tokens":
            log.warning("  Chunk %d/%d still truncated — consider reducing CHUNK_SIZE.",
                        i + 1, len(chunks))
        new_count = 0
        for r in (recs or []):
            sid = r.get("sample_id", "")
            if sid and sid not in seen_ids:
                seen_ids.add(sid)
                all_records.append(r)
                new_count += 1
        log.info("  -> %d new records (total so far: %d)", new_count, len(all_records))

    log.info("Chunked extraction complete: %d unique records from %d chunks",
             len(all_records), len(chunks))
    return all_records, total_tokens


def normalise_extracted(records: list[dict], doi: str, config: dict) -> list[dict]:
    """Post-process LLM output: enforce schema fields, compute delta, add flags."""
    normalised = []
    for r in records:
        d16 = r.get("d13C_16_0")
        d18 = r.get("d13C_18_0")
        if d16 is None or d18 is None:
            log.warning("  Skipping row (missing d13C): %s", r.get("sample_id"))
            continue

        try:
            d16, d18 = float(d16), float(d18)
        except (ValueError, TypeError):
            log.warning("  Skipping row (non-numeric d13C): %s", r.get("sample_id"))
            continue

        delta = compute_delta(d18, d16)
        flags = plausibility_flags(d16, d18, delta)
        if r.get("extraction_confidence") == "low":
            flags.append("low_confidence_extraction")

        region = r.get("region") or config.get("region_default") or "Britain"

        rec = {
            "sample_id": str(r.get("sample_id", "unknown")).strip(),
            "source": {
                "citation":         config["citation"],
                "doi":              doi,
                "table_or_figure":  r.get("table_or_figure") or config["table_or_figure"],
                "extraction_route": "tierB_llm",
            },
            "region":       region,
            "site":         str(r.get("site") or "unknown").strip(),
            "site_lat":     None,
            "site_long":    None,
            "context":      r.get("context"),
            "ceramic_type": r.get("ceramic_type") or "unknown",
            "period":       r.get("period") or "Neolithic (unspec)",
            "date_range_bce": r.get("date_range_bce"),
            "d13C_16_0":    d16,
            "d13C_18_0":    d18,
            "delta_13C":    delta,
            "d2H_16_0":     float(r["d2H_16_0"]) if r.get("d2H_16_0") is not None else None,
            "author_assignment": r.get("author_assignment"),
            "analytical": {
                "extraction_method": None,
                "derivatisation":    None,
                "instrument":        "GC-C-IRMS",
                "lab":               None,
            },
            "qa": {
                "value_from":           r.get("value_from", "table"),
                "extraction_confidence": r.get("extraction_confidence", "high"),
                "flags": flags,
            },
        }
        normalised.append(rec)
    return normalised


# ─── Per-paper orchestration ───────────────────────────────────────────────────

def process_paper(client: anthropic.Anthropic, doi: str):
    config = CORPUS[doi]
    citation = config["citation"]
    slug = doi_to_slug(doi)

    log.info("=" * 60)
    log.info("Processing: %s (%s)", citation, doi)

    # Locate PDF
    pdf_path = find_pdf(config["pdf_hint"], DATA_DIR)
    if pdf_path is None:
        log.error("PDF not found in %s (hint: %s). Skipping.", DATA_DIR, config["pdf_hint"])
        return

    log.info("PDF: %s", pdf_path.name)
    pdf_text = extract_pdf_text(pdf_path)
    log.info("Extracted %d chars from PDF", len(pdf_text))

    # Stage 1: triage (Haiku)
    t0 = time.time()
    triage_result, triage_tokens = triage(client, pdf_text)
    triage_elapsed = time.time() - t0
    log.info("Triage (%s, %.1fs, %d tok): has_data=%s, tables=%s",
             MODEL_TRIAGE, triage_elapsed, triage_tokens,
             triage_result.get("has_compound_specific_data"),
             triage_result.get("tables_with_d13C"))

    if not triage_result.get("has_compound_specific_data"):
        log.warning("Triage found no compound-specific δ¹³C data. Notes: %s",
                    triage_result.get("notes"))
        save_extracted(slug, [], meta={
            "citation": citation, "doi": doi, "halted_at": "triage",
            "triage": triage_result,
        })
        return

    target_tables = triage_result.get("tables_with_d13C", [])
    if triage_result.get("figures_with_d13C"):
        log.info("Figures with δ¹³C (excluded, Tier C): %s",
                 triage_result["figures_with_d13C"])

    # Stage 2: extract (Sonnet)
    t0 = time.time()
    raw_records, extract_tokens = extract_records(client, pdf_text, doi, config, target_tables)
    extract_elapsed = time.time() - t0
    log.info("Extract (%s, %.1fs, %d tok): %d raw records",
             MODEL_EXTRACT, extract_elapsed, extract_tokens, len(raw_records))

    total_tokens = triage_tokens + extract_tokens
    log.info("Paper total tokens: %d", total_tokens)

    # Normalise
    records = normalise_extracted(raw_records, doi, config)
    log.info("Normalised: %d records (dropped %d malformed)",
             len(records), len(raw_records) - len(records))

    valid, invalid = validate_records(records)
    if invalid:
        log.warning("%d records failed schema validation:", len(invalid))
        for r in invalid:
            log.warning("  %s: %s", r.get("sample_id"), r.get("validation_errors"))

    meta = {
        "citation": citation,
        "doi": doi,
        "pdf_file": pdf_path.name,
        "triage": triage_result,
        "tokens": {"triage": triage_tokens, "extract": extract_tokens, "total": total_tokens},
        "record_count": len(records),
        "valid": len(valid),
        "invalid": len(invalid),
    }
    if config.get("raw_deposit"):
        meta["raw_deposit"] = config["raw_deposit"]
    out_path = save_extracted(slug, records, meta=meta)
    log.info("Saved %d records → %s", len(records), out_path)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doi", type=str, help="Extract a single DOI")
    parser.add_argument("--all", action="store_true", help="Extract all configured Tier B papers")
    parser.add_argument("--list", action="store_true", help="List configured papers and exit")
    args = parser.parse_args()

    if args.list:
        for doi, cfg in CORPUS.items():
            print(f"  {cfg['citation']:30s}  {doi}")
        return

    client = anthropic.Anthropic()

    if args.doi:
        if args.doi in EXCLUDED_DOIS:
            log.error("DOI %s is on the hard-exclude list: %s", args.doi, EXCLUDED_DOIS[args.doi])
            sys.exit(1)
        if args.doi not in CORPUS:
            log.error("Unknown DOI: %s\nConfigured: %s", args.doi, list(CORPUS.keys()))
            sys.exit(1)
        process_paper(client, args.doi)
    elif args.all:
        # Iterate the authoritative SEED_DOIS list; skip any DOI handled by Tier A.
        for doi in SEED_DOIS:
            if doi not in CORPUS:
                log.info("Skipping %s (not in Tier B CORPUS — handled by Tier A or deferred)", doi)
                continue
            process_paper(client, doi)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
