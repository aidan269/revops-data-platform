-- Raw lead landing zone — append-only "bronze" layer.
-- Every inbound form/lead payload lands here UNTOUCHED, before any mapping.
-- This is the record that would have made the 138 UTM corruption recoverable.

CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.leads_raw (
    event_id      STRING        NOT NULL,                          -- idempotency key (PK)
    received_at   TIMESTAMP_NTZ NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    source        STRING,                                          -- 'web3_scoping_form' | 'google_ads' | 'make' | ...
    form_id       STRING,                                          -- HubSpot form GUID / page id
    raw_payload   VARIANT       NOT NULL,                          -- the WHOLE untouched payload + full querystring
    record_hash   STRING,                                          -- sha256 of normalized payload, for dedupe
    status        STRING        DEFAULT 'raw',                     -- raw -> mapped -> error
    processed_at  TIMESTAMP_NTZ,
    CONSTRAINT pk_leads_raw PRIMARY KEY (event_id)
);

-- Idempotent upsert (so replays never double-write):
MERGE INTO raw.leads_raw t
USING (SELECT :event_id AS event_id) s
   ON t.event_id = s.event_id
WHEN NOT MATCHED THEN
    INSERT (event_id, source, form_id, raw_payload, record_hash)
    VALUES (:event_id, :source, :form_id, PARSE_JSON(:raw_payload), :record_hash);
