-- HubSpot deals extract tables — append-only snapshot pattern.
-- Extends 02_hubspot_raw.sql for Task 4.

CREATE TABLE IF NOT EXISTS raw.hubspot_deals (
    id                  TEXT        NOT NULL,
    extracted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    amount              NUMERIC(18,2),
    dealstage           TEXT,
    pipeline            TEXT,
    hs_is_closed_won    BOOLEAN,
    createdate          TIMESTAMPTZ,
    closedate           TIMESTAMPTZ,
    deal_source         TEXT,
    deal_owner_id       TEXT,
    next_step           TEXT,
    next_step_updated_at TIMESTAMPTZ,
    product_service     TEXT,
    billing_model       TEXT,
    raw_properties      JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- Existing local databases predate Deal Source. This keeps the migration safe
-- on both fresh and already-initialized environments.
ALTER TABLE raw.hubspot_deals
    ADD COLUMN IF NOT EXISTS deal_source TEXT;
ALTER TABLE raw.hubspot_deals ADD COLUMN IF NOT EXISTS deal_owner_id TEXT;
ALTER TABLE raw.hubspot_deals ADD COLUMN IF NOT EXISTS next_step TEXT;
ALTER TABLE raw.hubspot_deals ADD COLUMN IF NOT EXISTS next_step_updated_at TIMESTAMPTZ;
ALTER TABLE raw.hubspot_deals ADD COLUMN IF NOT EXISTS product_service TEXT;
ALTER TABLE raw.hubspot_deals ADD COLUMN IF NOT EXISTS billing_model TEXT;

CREATE TABLE IF NOT EXISTS raw.hubspot_deal_contacts (
    deal_id             TEXT        NOT NULL,
    contact_id          TEXT        NOT NULL,
    extracted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hs_deals_id       ON raw.hubspot_deals (id, extracted_at);
CREATE INDEX IF NOT EXISTS idx_hs_deal_contacts  ON raw.hubspot_deal_contacts (deal_id, contact_id);

COMMENT ON TABLE raw.hubspot_deals        IS 'Append-only HubSpot deal snapshots. hs_is_closed_won carried as-is from HubSpot.';
COMMENT ON TABLE raw.hubspot_deal_contacts IS 'Deal-to-contact associations. Links deals to contacts for channel attribution.';
