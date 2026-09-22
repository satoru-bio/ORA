"""
03_validate.py — Full corpus validation.

Checks (in order):
  1. Provenance completeness — zero records without citation + table_or_figure (build-fails if any)
  2. Plausibility — δ¹³C values within NW-Euro C3 envelope; Δ¹³C within expected range
  3. Author-agreement — computed band vs author_assignment; report % and all disagreements
  4. Held-out ground truth — see --held-out flag
  5. Negative probe — aquatic/marine records must not silently land in dairy or non-ruminant
     (reports position, does not suppress)
  6. Value provenance — reused values carry original_doi; original_record_id, when set,
     must point at a record in the corpus. Summary statistics count independent records only.

Exits non-zero on any ERROR-level finding.

Usage:
    python pipeline/03_validate.py
    python pipeline/03_validate.py --held-out 10.1073/pnas.0335955100
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline.common import (
    EXTRACTED_DIR, all_extracted_slugs, author_agrees, band_of,
    D13C_MAX, D13C_MIN, DELTA_MAX, DELTA_MIN, is_independent, load_extracted,
    validate_records,
)


def load_all_records() -> list[dict]:
    records = []
    for slug in all_extracted_slugs():
        data = load_extracted(slug)
        records.extend(data.get("records", []))
    return records


# ─── Check 1: Provenance completeness ────────────────────────────────────────

def check_provenance(records: list[dict]) -> list[str]:
    """Fail build if any record lacks citation or table_or_figure."""
    errors = []
    for r in records:
        src = r.get("source") or {}
        if not src.get("citation"):
            errors.append(f"  MISSING citation: {r.get('sample_id')} / {r.get('site')}")
        if not src.get("table_or_figure"):
            errors.append(f"  MISSING table_or_figure: {r.get('sample_id')} / {src.get('citation')}")
    return errors


# ─── Check 2: Schema validation ───────────────────────────────────────────────

def check_schema(records: list[dict]) -> list[str]:
    _, invalid = validate_records(records)
    return [f"  SCHEMA {r['sample_id']}: {r['validation_errors']}" for r in invalid]


# ─── Check 3: Plausibility ────────────────────────────────────────────────────

def check_plausibility(records: list[dict]) -> list[str]:
    warnings = []
    for r in records:
        d16 = r.get("d13C_16_0")
        d18 = r.get("d13C_18_0")
        delta = r.get("delta_13C")
        sid = r.get("sample_id")
        cit = (r.get("source") or {}).get("citation", "?")
        if d16 is not None and not (D13C_MIN <= d16 <= D13C_MAX):
            warnings.append(f"  WARN d16 out of C3 range: {sid} ({cit}): {d16}")
        if d18 is not None and not (D13C_MIN <= d18 <= D13C_MAX):
            warnings.append(f"  WARN d18 out of C3 range: {sid} ({cit}): {d18}")
        if delta is not None and not (DELTA_MIN <= delta <= DELTA_MAX):
            warnings.append(f"  WARN Δ¹³C out of range: {sid} ({cit}): {delta}")
    return warnings


# ─── Check 4: Author-agreement ────────────────────────────────────────────────

def check_author_agreement(records: list[dict]) -> tuple[dict[str, dict], list[str]]:
    """
    Returns:
      - per_paper_stats: {citation: {total, agrees, disagrees, pct_agreement}}
      - disagreement_lines: human-readable list of every disagrement
    """
    from collections import defaultdict
    stats: dict[str, dict] = defaultdict(lambda: {"total": 0, "agrees": 0, "disagrees": 0})
    disagreements = []

    for r in records:
        aa = r.get("author_assignment")
        delta = r.get("delta_13C")
        cit = (r.get("source") or {}).get("citation", "?")
        sid = r.get("sample_id")
        if aa is None or delta is None:
            continue
        result = author_agrees(aa, delta)
        if result is None:
            continue  # not mappable (aquatic, mixed, none)
        stats[cit]["total"] += 1
        if result:
            stats[cit]["agrees"] += 1
        else:
            stats[cit]["disagrees"] += 1
            computed = band_of(delta)
            disagreements.append(
                f"  DISAGREE {sid} ({cit}): "
                f"author='{aa}' computed='{computed}' Δ¹³C={delta:.2f}"
            )

    for cit, s in stats.items():
        t = s["total"]
        s["pct_agreement"] = round(100 * s["agrees"] / t, 1) if t else 0

    return dict(stats), disagreements


# ─── Check 6: Value provenance ───────────────────────────────────────────────

def check_value_provenance(records: list[dict]) -> list[str]:
    """
    Reused values must name the original publication; original_record_id, when set,
    must resolve to (sample_id, doi) = (original_record_id, original_doi) in the corpus.
    """
    errors = []
    keys = {(r.get("sample_id"), (r.get("source") or {}).get("doi")) for r in records}
    for r in records:
        sid = r.get("sample_id")
        own_doi = (r.get("source") or {}).get("doi")
        pov = r.get("provenance_of_value")
        odoi = r.get("original_doi")
        orid = r.get("original_record_id")
        if pov == "reused":
            if not odoi:
                errors.append(f"  REUSED without original_doi: {sid} ({own_doi})")
            elif odoi == own_doi:
                errors.append(f"  REUSED original_doi equals own doi: {sid} ({own_doi})")
            if orid is not None and (orid, odoi) not in keys:
                errors.append(f"  original_record_id not in corpus: {sid} -> {orid} ({odoi})")
        elif odoi is not None or orid is not None:
            errors.append(f"  ORIGINAL value carries original_doi/original_record_id: {sid} ({own_doi})")
    return errors


# ─── Check 5: Negative probe (aquatic) ───────────────────────────────────────

def check_aquatic_probe(records: list[dict]) -> list[str]:
    """
    Report where aquatic-assigned records plot.
    The tool must not silently assign them to dairy or non-ruminant.
    This check is informational — it does not fail the build.
    """
    notes = []
    for r in records:
        aa = r.get("author_assignment")
        if aa != "aquatic":
            continue
        delta = r.get("delta_13C")
        if delta is None:
            continue
        computed = band_of(delta)
        cit = (r.get("source") or {}).get("citation", "?")
        notes.append(
            f"  AQUATIC probe: {r.get('sample_id')} ({cit}) "
            f"Δ¹³C={delta:.2f} plots within '{computed}' field"
        )
    return notes


# ─── Held-out ground truth ────────────────────────────────────────────────────

def held_out_check(records: list[dict], held_out_doi: str):
    """
    For the held-out paper: compute the per-band assignment and compare to author calls.
    Print a confusion table.
    """
    subset = [r for r in records
              if (r.get("source") or {}).get("doi") == held_out_doi
              and r.get("author_assignment") is not None
              and r.get("author_assignment") not in ("aquatic", "mixed", "none")]
    if not subset:
        print(f"  No records found for held-out DOI: {held_out_doi}")
        return

    tp = fp = fn = 0
    from collections import Counter
    confusion: dict[tuple[str, str], int] = Counter()
    for r in subset:
        aa = r["author_assignment"]
        computed = band_of(r["delta_13C"])
        confusion[(aa, computed)] += 1
        if aa == computed:
            tp += 1
        else:
            fp += 1

    total = len(subset)
    pct = 100 * tp / total if total else 0
    print(f"\n  Held-out ground truth ({held_out_doi}):")
    print(f"  Total assignable records: {total}")
    print(f"  Agrees: {tp} / {total} = {pct:.1f}%")
    print("\n  Confusion matrix (author → computed):")
    for (author, computed), count in sorted(confusion.items()):
        marker = "" if author == computed else " ← DISAGREE"
        print(f"    {author:25s} → {computed:25s}  n={count}{marker}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--held-out", type=str, default=None,
                        help="DOI of paper to use for held-out ground truth check")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress WARN-level output (ERRORs still shown)")
    args = parser.parse_args()

    print(f"Loading records from {EXTRACTED_DIR} ...")
    records = load_all_records()
    print(f"  {len(records)} records across {len(all_extracted_slugs())} extraction files\n")

    errors: list[str] = []
    warnings: list[str] = []

    # ── 1. Provenance ─────────────────────────────────────────────────────────
    print("─── 1. Provenance completeness ───────────────────────────────────")
    prov_errors = check_provenance(records)
    if prov_errors:
        print(f"  ERROR: {len(prov_errors)} records missing provenance (build FAILS):")
        for e in prov_errors:
            print(e)
        errors.extend(prov_errors)
    else:
        print(f"  OK — all {len(records)} records have citation + table_or_figure")

    # ── 2. Schema ─────────────────────────────────────────────────────────────
    print("\n─── 2. Schema validation ─────────────────────────────────────────")
    schema_errors = check_schema(records)
    if schema_errors:
        print(f"  {len(schema_errors)} schema violations:")
        for e in schema_errors[:20]:
            print(e)
        errors.extend(schema_errors)
    else:
        print("  OK")

    # ── 2b. Value provenance ──────────────────────────────────────────────────
    print("\n─── 2b. Value provenance ─────────────────────────────────────────")
    vp_errors = check_value_provenance(records)
    independent = [r for r in records if is_independent(r)]
    n_reused = sum(1 for r in records if r.get("provenance_of_value") == "reused")
    if vp_errors:
        print(f"  {len(vp_errors)} provenance errors:")
        for e in vp_errors:
            print(e)
        errors.extend(vp_errors)
    else:
        print(f"  OK — {len(records) - n_reused} original, {n_reused} reused; "
              f"{len(independent)} independent")

    # ── 3. Plausibility ───────────────────────────────────────────────────────
    print("\n─── 3. Plausibility (NW-Euro C3 envelope) ────────────────────────")
    plaus_warns = check_plausibility(records)
    if plaus_warns:
        print(f"  {len(plaus_warns)} out-of-range values (flagged, not dropped):")
        if not args.quiet:
            for w in plaus_warns:
                print(w)
        warnings.extend(plaus_warns)
    else:
        print("  OK — all δ¹³C values within expected C3 range")

    # ── 4. Author-agreement ───────────────────────────────────────────────────
    print("\n─── 4. Author-agreement (Δ¹³C band vs author_assignment) ─────────")
    ag_stats, disagreements = check_author_agreement(independent)
    overall_total = sum(s["total"] for s in ag_stats.values())
    overall_agrees = sum(s["agrees"] for s in ag_stats.values())
    overall_pct = 100 * overall_agrees / overall_total if overall_total else 0

    for cit, s in sorted(ag_stats.items()):
        print(f"  {cit:35s}  {s['pct_agreement']:5.1f}%  "
              f"({s['agrees']}/{s['total']}, {s['disagrees']} disagree)")
    print(f"\n  Overall: {overall_pct:.1f}% agreement ({overall_agrees}/{overall_total})")

    if disagreements:
        print(f"\n  All {len(disagreements)} disagreements:")
        if not args.quiet:
            for d in disagreements:
                print(d)
        warnings.extend(disagreements)
    else:
        print("  No disagreements")

    # ── 5. Aquatic probe ──────────────────────────────────────────────────────
    print("\n─── 5. Aquatic / negative probe ──────────────────────────────────")
    aquatic_notes = check_aquatic_probe(records)
    if aquatic_notes:
        print(f"  {len(aquatic_notes)} aquatic-assigned record(s) and where they plot:")
        for n in aquatic_notes:
            print(n)
        print("  NOTE: Δ¹³C cannot resolve aquatic/marine from non-ruminant. "
              "The frontend carries an explicit aquatic caveat.")
    else:
        print("  No aquatic-assigned records in corpus (or none with delta_13C).")

    # ── 6. Held-out ground truth ──────────────────────────────────────────────
    if args.held_out:
        print(f"\n─── 6. Held-out ground truth check ───────────────────────────")
        held_out_check(records, args.held_out)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n─── Summary ─────────────────────────────────────────────────────")
    print(f"  Total records: {len(records)} ({len(independent)} independent)")
    print(f"  ERRORs:  {len(errors)}")
    print(f"  WARNINGs: {len(warnings)}")

    if errors:
        print("\n  BUILD FAILED — fix errors before exporting.")
        sys.exit(1)
    else:
        print("\n  Validation passed. Proceed with: python pipeline/04_ingest_db.py")


if __name__ == "__main__":
    main()
