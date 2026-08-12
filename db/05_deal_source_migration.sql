-- One-time safe schema migration for an already running local warehouse.
-- Run before extract/extract_deals.py so the typed Deal Source value lands on
-- every append-only HubSpot deal snapshot.

ALTER TABLE raw.hubspot_deals
    ADD COLUMN IF NOT EXISTS deal_source TEXT;
