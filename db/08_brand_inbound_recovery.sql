-- BRAND-INBOUND-RECOVERY — append-only landing for historical human-maintained
-- brand inbound evidence.
--
-- Scope: local warehouse only. Nothing here creates, modifies, or deletes a
-- HubSpot record, and no association or attribution is ever written back.
--
-- These tables hold HISTORICAL EVIDENCE, not current CRM truth. They must never
-- be merged into raw.hubspot_* snapshot tables and must never silently supersede
-- the live snapshot. Every row carries authorizes_crm_change = false.

-- ---------------------------------------------------------------------------
-- Import / source metadata. One row per (source file, sha256).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.brand_inbound_imports (
    import_id            BIGSERIAL   PRIMARY KEY,
    source_kind          TEXT        NOT NULL,   -- 'csv_line_by_line' | 'pdf_twitter_crosscheck'
    source_filename      TEXT        NOT NULL,
    source_sha256        TEXT        NOT NULL,
    source_row_count     INTEGER,
    evidence_period      TEXT,                   -- human-maintained period the source covers
    evidence_observed_on DATE,                   -- date the evidence itself was observed
    imported_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorizes_crm_change BOOLEAN    NOT NULL DEFAULT false,
    notes                TEXT,
    CONSTRAINT brand_inbound_imports_uk UNIQUE (source_kind, source_sha256),
    CONSTRAINT brand_inbound_imports_no_crm_auth CHECK (authorizes_crm_change = false)
);

-- ---------------------------------------------------------------------------
-- All 353 CSV rows, preserved verbatim. Original values are TEXT exactly as
-- they appear in the file; parsed companions are added alongside, never in place.
-- Duplicate source rows remain individually observable via source_row_number.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.brand_inbound_lines (
    line_id                  BIGSERIAL   PRIMARY KEY,
    source_sha256            TEXT        NOT NULL,
    source_filename          TEXT        NOT NULL,
    source_row_number        INTEGER     NOT NULL,  -- 1-based data row, header excluded

    -- verbatim original columns
    month_raw                TEXT,
    deal_name_raw            TEXT,
    organisation_name_raw    TEXT,
    icp_fit_raw              TEXT,
    source_raw               TEXT,
    current_stage_raw        TEXT,
    solution_requested_raw   TEXT,
    call_booked_raw          TEXT,
    days_to_discovery_raw    TEXT,
    days_to_scope_complete_raw TEXT,
    days_to_call_booked_raw  TEXT,
    days_to_next_follow_up_raw TEXT,
    ae_name_raw              TEXT,
    deals_raw                TEXT,
    hubspot_link_raw         TEXT,
    gmv_raw                  TEXT,
    revenue_raw              TEXT,
    arr_raw                  TEXT,

    -- parsed companions (NULL whenever a safe parse is not possible)
    report_month_filled      TEXT,      -- fill-down of the sparse Month column
    hubspot_object_type      TEXT,      -- '0-3' deal, '0-2' company; never inferred
    hubspot_record_id        TEXT,
    is_deal_link             BOOLEAN,   -- true only for object type 0-3
    days_to_discovery_num    NUMERIC,
    days_to_scope_complete_num NUMERIC,
    days_to_call_booked_num  NUMERIC,
    days_to_next_follow_up_num NUMERIC,
    deals_num                NUMERIC,
    gmv_num                  NUMERIC,
    revenue_num              NUMERIC,
    arr_num                  NUMERIC,

    raw_row                  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    imported_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorizes_crm_change    BOOLEAN     NOT NULL DEFAULT false,
    CONSTRAINT brand_inbound_lines_uk UNIQUE (source_sha256, source_row_number),
    CONSTRAINT brand_inbound_lines_no_crm_auth CHECK (authorizes_crm_change = false),
    CONSTRAINT brand_inbound_lines_object_type CHECK (
        hubspot_object_type IS NULL OR hubspot_object_type IN ('0-3', '0-2')
    )
);

CREATE INDEX IF NOT EXISTS idx_brand_inbound_lines_record
    ON raw.brand_inbound_lines (hubspot_record_id);
CREATE INDEX IF NOT EXISTS idx_brand_inbound_lines_source
    ON raw.brand_inbound_lines (source_raw);

-- ---------------------------------------------------------------------------
-- Twitter / X cross-check evidence, one row per CSV Twitter deal (29).
--
-- The PDF identifies deals by NAME ONLY; it contains no HubSpot record IDs.
-- deal_id here is resolved by deal-name correspondence against the CSV, which is
-- why name_match_exact is carried explicitly. Rows with no PDF counterpart are
-- NOT_CROSSCHECKED — neither clean nor corrupted.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw.brand_inbound_twitter_crosscheck (
    crosscheck_id            BIGSERIAL   PRIMARY KEY,
    csv_source_sha256        TEXT        NOT NULL,
    pdf_source_sha256        TEXT,
    pdf_source_filename      TEXT,
    deal_id                  TEXT        NOT NULL,
    csv_deal_name            TEXT        NOT NULL,
    csv_organisation_name    TEXT,
    csv_source_value         TEXT        NOT NULL,  -- historical source, verbatim
    crosscheck_status        TEXT        NOT NULL,  -- CROSSCHECKED | NOT_CROSSCHECKED
    pdf_deal_name            TEXT,
    pdf_current_source       TEXT,                  -- PDF-observed current HubSpot source
    overwrite_status         TEXT,                  -- OVERWRITTEN | STILL_INTACT | NULL
    observed_mechanism       TEXT,                  -- observed drill-down label, not a cause
    observed_creation_source TEXT,                  -- record source at creation
    closed_won_flag          TEXT,
    name_match_exact         BOOLEAN,
    evidence_date            DATE,
    evidence_limitations     TEXT        NOT NULL,
    imported_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorizes_crm_change    BOOLEAN     NOT NULL DEFAULT false,
    CONSTRAINT brand_inbound_crosscheck_uk UNIQUE (csv_source_sha256, deal_id),
    CONSTRAINT brand_inbound_crosscheck_no_crm_auth CHECK (authorizes_crm_change = false),
    CONSTRAINT brand_inbound_crosscheck_status CHECK (
        crosscheck_status IN ('CROSSCHECKED', 'NOT_CROSSCHECKED')
    ),
    CONSTRAINT brand_inbound_crosscheck_overwrite CHECK (
        overwrite_status IS NULL OR overwrite_status IN ('OVERWRITTEN', 'STILL_INTACT')
    )
);

CREATE INDEX IF NOT EXISTS idx_brand_inbound_crosscheck_deal
    ON raw.brand_inbound_twitter_crosscheck (deal_id);

COMMENT ON TABLE raw.brand_inbound_imports IS
    'BRAND-INBOUND-RECOVERY source metadata. Historical evidence only; authorizes no CRM change.';
COMMENT ON TABLE raw.brand_inbound_lines IS
    'All 353 CSV rows verbatim with parsed companions. Never merged into hubspot_* snapshots.';
COMMENT ON TABLE raw.brand_inbound_twitter_crosscheck IS
    'Twitter/X historical-vs-PDF cross-check. PDF carries no deal IDs; IDs resolved by deal name.';
COMMENT ON COLUMN raw.brand_inbound_twitter_crosscheck.observed_mechanism IS
    'Observed HubSpot drill-down label only. It is not a causal attribution and does not name Zapier.';
