# RevOps Raw-Data Platform

Read-only ingestion of HubSpot source data into an append-only PostgreSQL
warehouse. HubSpot stays the system of record; this repository only *copies*
history out of it.


## Retained sources and raw tables

| Extractor | Raw tables |
| --- | --- |
| `extract/extract_hubspot.py` | `raw.hubspot_contacts`, `raw.hubspot_companies`, `raw.hubspot_contact_company_map` |
| `extract/extract_deals.py` | `raw.hubspot_deals`, `raw.hubspot_deal_contacts` |
| `extract/extract_pipeline_metadata.py` | `raw.hubspot_deal_stages` |
| `extract/extract_gtm_campaigns.py` | `raw.hubspot_gtm_campaigns`, `raw.hubspot_gtm_campaign_contacts`, `raw.hubspot_gtm_campaign_deals` |

`db/04_hubspot_campaigns.sql` also provisions the native-campaign tables
(`raw.hubspot_campaigns`, `raw.hubspot_campaign_members`,
`raw.hubspot_engagements`). See *Known gaps* below.

## Local setup

```bash
docker compose up -d          # PostgreSQL, with the raw schema initialized
pip install -r requirements.txt
```

`db/init.sql` and `db/02_hubspot_raw.sql` run automatically on **first**
initialization of the volume.

## Migrations

```bash
python scripts/run_db_migrations.py
```

Applies `03_hubspot_deals.sql`, `04_hubspot_campaigns.sql`,
`06_original_traffic_source.sql`, and `07_gtm_campaigns.sql` in that order under
an advisory lock, recording each filename and SHA-256 checksum in
`analytics.schema_migrations`. Re-running verifies checksums and skips
completed files; it fails closed on a missing file, a SQL error, or a checksum
change. Details: [reference/local_database_migrations.md](reference/local_database_migrations.md).

## Mock extraction

`extract_hubspot.py` and `extract_deals.py` accept `--mock` to land synthetic
rows that match the real schema, so the warehouse can be exercised without a
token:

```bash
python extract/extract_hubspot.py --mock
python extract/extract_deals.py --mock
```

`extract_gtm_campaigns.py` has no mock mode; use `--dry-run` to print the
request scope without calling HubSpot.

## Live extraction requirements

Live runs need `HUBSPOT_PRIVATE_APP_TOKEN` and `DATABASE_URL` in the
environment, plus read scopes for the objects being extracted
(`crm.objects.custom.read` for GTM Campaigns, and contacts/deals read scope for
association ids). Apply migrations first — each extractor checks its required
tables and columns and fails closed with the migration command if the schema is
stale.

## Read-only boundary

- Every HubSpot call is a `GET`. No extractor creates, updates, archives, or
  deletes a CRM record, and none writes an association.
- Landing tables are append-only: each run appends a snapshot with
  `extracted_at`. Nothing updates or deletes prior raw history.
- Association edges are copied exactly as HubSpot reports them; none are
  inferred from UTM parameters, clicks, or contact membership.
- Campaign names are read from the source; a blank name stays null rather than
  being invented.

`tests/test_db_migrations.py` enforces these boundaries, including the absence
of any write-back module or non-GET HTTP call.
