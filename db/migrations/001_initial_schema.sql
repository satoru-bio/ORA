-- ORA: Organic Residue Archive
-- British and Irish Neolithic pottery lipid residue — compound-specific δ¹³C corpus
-- PostgreSQL 16 + PostGIS 3.4

CREATE EXTENSION IF NOT EXISTS postgis;

-- ─── Main records table ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS residue_records (
    id                   SERIAL PRIMARY KEY,

    -- Identity: the paper's own label for the sherd or vessel
    sample_id            TEXT        NOT NULL,

    -- Provenance (non-negotiable; build fails if null — see 03_validate.py)
    citation             TEXT        NOT NULL,
    doi                  TEXT        NOT NULL,
    table_or_figure      TEXT        NOT NULL,
    extraction_route     TEXT        NOT NULL
                             CHECK (extraction_route IN ('tierA_parse', 'tierB_llm', 'tierC_figure')),

    -- Location
    region               TEXT        NOT NULL
                             CHECK (region IN ('Britain', 'Ireland')),
    site                 TEXT        NOT NULL,
    site_location        GEOMETRY(POINT, 4326),   -- WGS-84; NULL until geocoded
    context              TEXT,

    -- Ceramic classification
    ceramic_type         TEXT        NOT NULL DEFAULT 'unknown',
    period               TEXT        NOT NULL
                             CHECK (period IN (
                                 'Early Neolithic',
                                 'Middle Neolithic',
                                 'Late Neolithic',
                                 'Neolithic (unspec)'
                             )),
    date_range_from      INTEGER,    -- BCE (positive integer)
    date_range_to        INTEGER,    -- BCE (positive integer, ≤ date_range_from)

    -- Compound-specific δ¹³C (per mille, ‰)
    d13C_16_0            NUMERIC(7,2) NOT NULL,
    d13C_18_0            NUMERIC(7,2) NOT NULL,
    -- Δ¹³C computed deterministically; never null when both FAs present
    delta_13C            NUMERIC(7,2) GENERATED ALWAYS AS (d13C_18_0 - d13C_16_0) STORED,
    d2H_16_0             NUMERIC(7,2),            -- capture if present

    -- Author's own commodity assignment (stored exactly as stated; never overwritten by tool)
    author_assignment    TEXT
                             CHECK (author_assignment IN (
                                 'ruminant dairy',
                                 'ruminant adipose',
                                 'non-ruminant/porcine',
                                 'aquatic',
                                 'mixed',
                                 'none',
                                 NULL
                             )),

    -- Analytical metadata
    extraction_method    TEXT,
    derivatisation       TEXT,
    instrument           TEXT,
    lab                  TEXT,

    -- QA
    value_from           TEXT        NOT NULL DEFAULT 'table'
                             CHECK (value_from IN ('table', 'figure', 'text')),
    extraction_confidence TEXT       NOT NULL DEFAULT 'high'
                             CHECK (extraction_confidence IN ('high', 'medium', 'low')),
    flags                TEXT[],

    -- Bookkeeping
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- One record per sherd per paper
    UNIQUE (sample_id, doi)
);

-- Spatial index for future map view
CREATE INDEX IF NOT EXISTS residue_records_site_location_idx
    ON residue_records USING GIST (site_location);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS residue_records_doi_idx       ON residue_records (doi);
CREATE INDEX IF NOT EXISTS residue_records_region_idx    ON residue_records (region);
CREATE INDEX IF NOT EXISTS residue_records_period_idx    ON residue_records (period);
CREATE INDEX IF NOT EXISTS residue_records_site_idx      ON residue_records (site);

-- ─── Extraction log ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS extraction_log (
    id             SERIAL PRIMARY KEY,
    doi            TEXT        NOT NULL,
    stage          TEXT        NOT NULL,
    model_used     TEXT,
    prompt_tokens  INTEGER,
    completion_tokens INTEGER,
    elapsed_s      NUMERIC(8,2),
    flags          TEXT[],
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
