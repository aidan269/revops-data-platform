-- Raw + analytics schemas for the RevOps warehouse (Postgres).
-- Runs automatically on first `docker compose up` (mounted into the postgres image).

CREATE SCHEMA IF NOT EXISTS raw;         -- immutable "bronze" landing
CREATE SCHEMA IF NOT EXISTS analytics;   -- dbt marts/views that people + Hermes read

-- Append-only landing table. Never edited. Corruption stays replayable.
CREATE TABLE IF NOT EXISTS raw.leads_raw (
    event_id     TEXT PRIMARY KEY,               -- idempotency key
    received_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    source       TEXT,                            -- form / channel / make / webhook
    form_id      TEXT,                            -- HubSpot form GUID / page id
    raw_payload  JSONB NOT NULL,                  -- whole untouched payload + querystring
    record_hash  TEXT,                            -- dedupe / idempotent upsert
    status       TEXT DEFAULT 'raw',              -- raw -> mapped -> error
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_leads_raw_received ON raw.leads_raw (received_at);

-- A write-back audit log so every controlled push to HubSpot is recorded.
CREATE TABLE IF NOT EXISTS analytics.hubspot_writeback_log (
    id           BIGSERIAL PRIMARY KEY,
    written_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    object_type  TEXT,                            -- contact / company / deal
    object_id    TEXT,                             -- HubSpot object id
    field        TEXT,                             -- must be on the whitelist
    old_value    TEXT,
    new_value    TEXT,
    dry_run      BOOLEAN NOT NULL DEFAULT true     -- true = simulated, false = live
);
