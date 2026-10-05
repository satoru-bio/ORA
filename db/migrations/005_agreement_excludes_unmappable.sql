-- 005: align author-agreement statistics with 03_validate.py
--
-- 'mixed', 'none' and 'aquatic' author assignments cannot be produced by ORA's
-- 1D Δ¹³C bands, so they are unmappable: they are excluded from the agreement
-- statistic rather than counted as disagreements. Records with no author
-- assignment are excluded as before. Only 'ruminant dairy', 'ruminant adipose'
-- and 'non-ruminant/porcine' are compared (common.ASSIGNMENT_TO_BAND).
--
-- Supersedes the view definitions in 002 and 003; those files are left as
-- written.

-- Both views are dropped and recreated: residue_with_band selects r.*, which
-- gained qa_notes in 004, and the summary's column set changes
-- (total_with_assignment -> total_mappable, plus exclusion counts).
DROP VIEW IF EXISTS author_agreement_summary;
DROP VIEW IF EXISTS residue_with_band;

-- band_agrees_with_author: NULL (not FALSE) for unmappable assignments.
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
        WHEN r.author_assignment NOT IN
             ('ruminant dairy', 'ruminant adipose', 'non-ruminant/porcine') THEN NULL
        WHEN r.delta_13C > -1.0  AND r.author_assignment = 'non-ruminant/porcine' THEN TRUE
        WHEN r.delta_13C < -3.1  AND r.author_assignment = 'ruminant dairy'       THEN TRUE
        WHEN r.delta_13C BETWEEN -3.1 AND -1.0
             AND r.author_assignment = 'ruminant adipose'                          THEN TRUE
        ELSE FALSE
    END AS band_agrees_with_author
FROM residue_records r;

-- Independent records only (original_record_id IS NULL).
CREATE VIEW author_agreement_summary AS
SELECT
    citation,
    COUNT(*) FILTER (WHERE band_agrees_with_author IS NOT NULL) AS total_mappable,
    COUNT(*) FILTER (WHERE band_agrees_with_author = TRUE)      AS agrees,
    COUNT(*) FILTER (WHERE band_agrees_with_author = FALSE)     AS disagrees,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE band_agrees_with_author = TRUE)
        / NULLIF(COUNT(*) FILTER (WHERE band_agrees_with_author IS NOT NULL), 0),
        1
    ) AS pct_agreement,
    COUNT(*) FILTER (WHERE author_assignment = 'mixed')   AS excluded_mixed,
    COUNT(*) FILTER (WHERE author_assignment = 'none')    AS excluded_none,
    COUNT(*) FILTER (WHERE author_assignment = 'aquatic') AS excluded_aquatic,
    COUNT(*) FILTER (WHERE author_assignment IS NULL)     AS excluded_no_assignment
FROM residue_with_band
WHERE original_record_id IS NULL
GROUP BY citation
ORDER BY citation;
