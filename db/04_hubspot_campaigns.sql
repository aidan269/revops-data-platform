-- HubSpot campaigns + engagements extract tables — append-only snapshot pattern.
-- Extends 03_hubspot_deals.sql for Task 5.

CREATE TABLE IF NOT EXISTS raw.hubspot_campaigns (
    id              TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    name            TEXT,
    type            TEXT,
    raw_properties  JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS raw.hubspot_campaign_members (
    campaign_id     TEXT        NOT NULL,
    contact_id      TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.hubspot_engagements (
    id              TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    contact_id      TEXT        NOT NULL,
    type            TEXT        NOT NULL,
    timestamp        TIMESTAMPTZ NOT NULL,
    campaign_id     TEXT,
    asset_id        TEXT,
    raw_properties  JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_hs_campaigns_id     ON raw.hubspot_campaigns (id, extracted_at);
CREATE INDEX IF NOT EXISTS idx_hs_campaign_members  ON raw.hubspot_campaign_members (campaign_id, contact_id);
CREATE INDEX IF NOT EXISTS idx_hs_engagements_contact ON raw.hubspot_engagements (contact_id, timestamp);

COMMENT ON TABLE raw.hubspot_campaigns       IS 'Append-only HubSpot campaign snapshots.';
COMMENT ON TABLE raw.hubspot_campaign_members IS 'Campaign-to-contact associations.';
COMMENT ON TABLE raw.hubspot_engagements      IS 'Append-only HubSpot engagement events (email_open, email_click, form_submission, meeting).';
