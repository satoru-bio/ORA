-- 004: qa_notes column
--
-- Optional free-text QA note (JSON schema: qa.qa_notes), e.g. the explanation
-- attached to AB30's value_verbatim_physically_implausible flag. Without this
-- column a DB-sourced export drops the note.
--
-- Existing rows get NULL. Populate by re-running
-- pipeline/04_ingest_db.py --clear-first.

ALTER TABLE residue_records
    ADD COLUMN IF NOT EXISTS qa_notes TEXT;
