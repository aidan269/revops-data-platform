-- AUTOMATION-DIGITAL-TWIN — refresh-safe versioning.
--
-- Forward migration. Migration 10 is already applied elsewhere and its checksum
-- must not change, so the refresh model is added here rather than edited in.
--
-- Problem this fixes: the initial loader used ON CONFLICT DO NOTHING, which meant
-- a row written once could never be corrected. An asset that changed state, an
-- edge that resolved, or a finding that cleared would be frozen at its first
-- observation forever.
--
-- Model: every load is recorded in raw.automation_loads. Each entity carries the
-- load that first saw it and the load that last saw it, plus a content hash.
-- Re-loading UPDATES last_seen_load and mutable columns instead of skipping.
-- History is preserved because entities are never deleted: an entity that stops
-- appearing simply keeps its older last_seen_load and drops out of "current".

CREATE TABLE IF NOT EXISTS raw.automation_loads (
    load_id            BIGSERIAL   PRIMARY KEY,
    collection_run_id  TEXT        NOT NULL,
    graph_content_hash TEXT,
    started_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_count       INTEGER,
    notes              TEXT,
    authorizes_external_write BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT al_no_write_ck CHECK (authorizes_external_write = false)
);

DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'automation_assets','automation_nodes','automation_edges',
        'automation_field_access','automation_findings','automation_runs',
        'automation_source_snapshots'
    ] LOOP
        EXECUTE format(
            'ALTER TABLE raw.%I
               ADD COLUMN IF NOT EXISTS first_seen_load BIGINT,
               ADD COLUMN IF NOT EXISTS last_seen_load  BIGINT,
               ADD COLUMN IF NOT EXISTS content_hash    TEXT,
               ADD COLUMN IF NOT EXISTS last_refreshed_at TIMESTAMPTZ', t);
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS idx_%s_last_seen ON raw.%I (last_seen_load)', t, t);
    END LOOP;
END
$$;

-- Convenience view: the most recent completed load.
CREATE OR REPLACE VIEW raw.automation_current_load AS
SELECT max(load_id) AS load_id FROM raw.automation_loads;

COMMENT ON TABLE raw.automation_loads IS
    'One row per graph load. Entities reference it so refreshes update rather than freeze.';
COMMENT ON VIEW raw.automation_current_load IS
    'Latest load id. Current-state marts filter last_seen_load to this value.';
