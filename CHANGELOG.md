# Changelog

## Known limitations

- **The web tool will count reused records as independent.** Frontend records (`frontend/public/corpus.json`) do not include `original_record_id`, so once any reused record exists, the web tool's record count will include it. Fixing this means changing the frontend record shape in `05_export.py` (`to_frontend_record`) and in `frontend/src/App.jsx`. **This must be fixed before the first reused record is ingested.**

## Unreleased

### Schema: value provenance and reference context (D-008)

Added before any expansion paper is ingested, following the decision to build ORA depth-first on the British and Irish literature.

- **New record fields:** `provenance_of_value`, `original_doi`, `original_record_id`, `prior_graphical_report`, `provenance_note` and `reference_context`. They appear in `corpus.json` and `corpus.csv`. The frontend record shape is unchanged.
- **`provenance_of_value` is defined by first numeric report.** `original` means this record's paper is the first to report the value numerically (tabulated or stated in text). `reused` means an earlier publication reported it numerically. A figure-only plot is not a numeric report. Reused values must give `original_doi`, and `original_record_id` too when the original record is in the corpus.
- **Independence rule.** A record is left out of independence-implying counts only when `original_record_id` is populated. The export meta gains `independent_record_count`. `03_validate.py` computes author-agreement statistics over independent records only. The DB view `author_agreement_summary` applies the same filter.
- **`reference_context`** defaults to `british_irish` so that other contexts can be added later without a migration. No per-context logic is attached.
- **Audit of the existing 327 records:** all are `original`. Copley 2005c's Windmill Hill, Hambledon Hill and Eton Rowing Lake records have `prior_graphical_report` set to Copley et al. 2003 (PNAS, 10.1073/pnas.0335955100). The Eton Rowing Lake records carry a note that only about 23 of the 37 were plotted. All Smyth & Evershed 2016 records carry a note that they have not been verified against the project's 2014 and 2015 sibling publications. Record counts and values are unchanged.
- **Database:** migration `db/migrations/003_value_provenance_reference_context.sql` adds the columns, a consistency constraint, the `residue_records_independent` view and the rebuilt validation views.

## 1.0 — 2026-08

- First release: 327 records from Copley et al. 2005c, Hammann et al. 2022 and Smyth & Evershed 2016. Code under MIT, data under CC-BY-4.0.
