-- 003: value provenance and reference context (decision D-008)
--
-- provenance_of_value is defined by first NUMERIC report (tabulated or stated in
-- text). A figure-only plot is not a numeric report; earlier plots go in
-- prior_graphical_report.
--
-- Independence rule: a record is excluded from independence-implying counts only
-- when original_record_id is populated, i.e. when the original record is itself
-- in the corpus (identified by original_record_id + original_doi).
--
-- Existing rows take the defaults ('original', 'british_irish'). The
-- prior_graphical_report / provenance_note annotations are populated by re-running
-- pipeline/04_ingest_db.py --clear-first from the updated extraction output.

ALTER TABLE residue_records
    ADD COLUMN IF NOT EXISTS provenance_of_value    TEXT NOT NULL DEFAULT 'original'
        CHECK (provenance_of_value IN ('original', 'reused')),
    ADD COLUMN IF NOT EXISTS original_doi           TEXT,
    ADD COLUMN IF NOT EXISTS original_record_id     TEXT,
    ADD COLUMN IF NOT EXISTS prior_graphical_report TEXT,
    ADD COLUMN IF NOT EXISTS provenance_note        TEXT,
    ADD COLUMN IF NOT EXISTS reference_context      TEXT NOT NULL DEFAULT 'british_irish';

ALTER TABLE residue_records
    DROP CONSTRAINT IF EXISTS residue_records_value_provenance_chk;
ALTER TABLE residue_records
    ADD CONSTRAINT residue_records_value_provenance_chk CHECK (
        (provenance_of_value = 'reused'   AND original_doi IS NOT NULL AND original_doi <> doi)
     OR (provenance_of_value = 'original' AND original_doi IS NULL AND original_record_id IS NULL)
    );

CREATE INDEX IF NOT EXISTS residue_records_reference_context_idx
    ON residue_records (reference_context);

-- ─── Independent records ──────────────────────────────────────────────────────

CREATE OR REPLACE VIEW residue_records_independent AS
SELECT * FROM residue_records
WHERE original_record_id IS NULL;

-- ─── Rebuild validation views ─────────────────────────────────────────────────
-- residue_with_band selects r.*, so it must be recreated to pick up the new
-- columns; author_agreement_summary depends on it and now counts independent
-- records only.

DROP VIEW IF EXISTS author_agreement_summary;
DROP VIEW IF EXISTS residue_with_band;

CREATE VIEW residue_with_band AS
SELECT
    r.*,
    CASE
        WHEN r.delta_13C > -1.0 THEN 'non-ruminant/porcine'
        WHEN r.delta_13C < -3.1 THEN 'ruminant dairy'
        ELSE 'ruminant adipose'
    END AS computed_band,
    CASE
        WHEN r.author_assignment IS NULL THEN NULL
        WHEN r.delta_13C > -1.0  AND r.author_assignment = 'non-ruminant/porcine' THEN TRUE
        WHEN r.delta_13C < -3.1  AND r.author_assignment = 'ruminant dairy'       THEN TRUE
        WHEN r.delta_13C BETWEEN -3.1 AND -1.0
             AND r.author_assignment = 'ruminant adipose'                          THEN TRUE
        ELSE FALSE
    END AS band_agrees_with_author
FROM residue_records r;

CREATE VIEW author_agreement_summary AS
SELECT
    citation,
    COUNT(*) FILTER (WHERE author_assignment IS NOT NULL) AS total_with_assignment,
    COUNT(*) FILTER (WHERE band_agrees_with_author = TRUE) AS agrees,
    COUNT(*) FILTER (WHERE band_agrees_with_author = FALSE) AS disagrees,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE band_agrees_with_author = TRUE)
        / NULLIF(COUNT(*) FILTER (WHERE author_assignment IS NOT NULL), 0),
        1
    ) AS pct_agreement
FROM residue_with_band
WHERE original_record_id IS NULL
GROUP BY citation
ORDER BY citation;
