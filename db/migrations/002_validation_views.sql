-- Validation views for 03_validate.py
-- Thresholds: Copley et al. 2003; Evershed et al. 2008

-- ─── Band assignment ──────────────────────────────────────────────────────────
-- Assigns each record to a commodity field based on Δ¹³C thresholds.
-- This is for validation against author_assignment only — the frontend
-- uses these same thresholds for the reference bands but never calls it "classification".

CREATE OR REPLACE VIEW residue_with_band AS
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

-- ─── Plausibility flags ───────────────────────────────────────────────────────
-- NW-Euro C3 reference frame: δ¹³C ≈ −34 to −22‰; Δ¹³C ≈ −7 to +2‰

CREATE OR REPLACE VIEW residue_plausibility AS
SELECT
    id, sample_id, citation, doi,
    d13C_16_0, d13C_18_0, delta_13C,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN d13C_16_0 NOT BETWEEN -34 AND -22 THEN 'd16_out_of_C3_range' END,
        CASE WHEN d13C_18_0 NOT BETWEEN -34 AND -22 THEN 'd18_out_of_C3_range' END,
        CASE WHEN delta_13C NOT BETWEEN -7 AND 2     THEN 'delta_out_of_range'  END
    ], NULL) AS plausibility_flags,
    flags AS extraction_flags
FROM residue_records;

-- ─── Author-agreement summary ─────────────────────────────────────────────────

CREATE OR REPLACE VIEW author_agreement_summary AS
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
GROUP BY citation
ORDER BY citation;
