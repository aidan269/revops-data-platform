-- HubSpot extract tables — append-only snapshot pattern.
-- Each extract run appends rows with an extracted_at timestamp.
-- Readers select the latest snapshot per id; rows are never updated in place.

CREATE TABLE IF NOT EXISTS raw.hubspot_contacts (
    id              TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    email           TEXT,
    jobtitle        TEXT,
    hs_seniority    TEXT,
    createdate      TIMESTAMPTZ,
    utm_source      TEXT,
    utm_medium      TEXT,
    utm_campaign    TEXT,
    raw_properties  JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS raw.hubspot_companies (
    id                  TEXT        NOT NULL,
    extracted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    name                TEXT,
    domain              TEXT,
    industry            TEXT,
    numberofemployees   INTEGER,
    hs_employee_range   TEXT,
    raw_properties      JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- Company-contact association (extracted alongside contacts)
CREATE TABLE IF NOT EXISTS raw.hubspot_contact_company_map (
    contact_id      TEXT        NOT NULL,
    company_id      TEXT        NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hs_contacts_id     ON raw.hubspot_contacts (id, extracted_at);
CREATE INDEX IF NOT EXISTS idx_hs_companies_id    ON raw.hubspot_companies (id, extracted_at);
CREATE INDEX IF NOT EXISTS idx_hs_contacts_email  ON raw.hubspot_contacts (email);

COMMENT ON TABLE raw.hubspot_contacts  IS 'Append-only HubSpot contact snapshots; select the latest row per id.';
COMMENT ON TABLE raw.hubspot_companies IS 'Append-only HubSpot company snapshots; select the latest row per id.';
