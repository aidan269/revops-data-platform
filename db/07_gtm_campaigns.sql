-- CRM-012 — read-only landing tables for the GTM Campaigns custom object.
--
-- HubSpot custom object type 2-63647366 ("GTM Campaigns"). This is NOT HubSpot's
-- native Marketing Campaign object; raw.hubspot_campaigns remains separate and
-- is never mixed with these tables.
--
-- Append-only, read-only ingestion only. Nothing here creates, modifies, or
-- deletes a HubSpot record, and no association is ever written back.

CREATE TABLE IF NOT EXISTS raw.hubspot_gtm_campaigns (
    id              TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    name            TEXT,
    created_at      TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ,
    archived        BOOLEAN,
    raw_properties  JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- Association edges. Membership alone is evidence of association, never of
-- attribution; see the CRM-012 methodology.
CREATE TABLE IF NOT EXISTS raw.hubspot_gtm_campaign_contacts (
    campaign_id     TEXT        NOT NULL,
    contact_id      TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.hubspot_gtm_campaign_deals (
    campaign_id     TEXT        NOT NULL,
    deal_id         TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gtm_campaigns_extracted
    ON raw.hubspot_gtm_campaigns (id, extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_gtm_campaign_contacts_extracted
    ON raw.hubspot_gtm_campaign_contacts (campaign_id, extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_gtm_campaign_deals_extracted
    ON raw.hubspot_gtm_campaign_deals (campaign_id, extracted_at DESC);

-- The Hermes MCP server connects as hermes_reader. Grants in this warehouse are
-- per-table rather than schema-wide defaults, so new tables must be granted
-- explicitly or the read-only tools cannot see them.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hermes_reader') THEN
        GRANT USAGE ON SCHEMA raw TO hermes_reader;
        GRANT SELECT ON raw.hubspot_gtm_campaigns TO hermes_reader;
        GRANT SELECT ON raw.hubspot_gtm_campaign_contacts TO hermes_reader;
        GRANT SELECT ON raw.hubspot_gtm_campaign_deals TO hermes_reader;
    END IF;
END
$$;
