-- CRM-010 — ingest native HubSpot deal Original Traffic Source.
--
-- Adds the typed column for the confirmed deal property hs_analytics_source so
-- every fresh read-only snapshot preserves it alongside deal_source. Read-only
-- extraction only; this migration authorizes no CRM change and no Deal Source
-- inference.

ALTER TABLE raw.hubspot_deals
    ADD COLUMN IF NOT EXISTS original_traffic_source TEXT;
