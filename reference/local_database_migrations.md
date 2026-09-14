# Local database migrations

Run the ordered migration runner before a live HubSpot extraction:

```bash
python scripts/run_db_migrations.py
```

## Retained migration set

The runner applies exactly these files, in this order:

| Order | File | Purpose |
| --- | --- | --- |
| 1 | `db/03_hubspot_deals.sql` | `raw.hubspot_deals` (plus nullable CRM-admin readiness columns) and `raw.hubspot_deal_contacts` |
| 2 | `db/04_hubspot_campaigns.sql` | `raw.hubspot_campaigns`, `raw.hubspot_campaign_members`, `raw.hubspot_engagements` |
| 3 | `db/06_original_traffic_source.sql` | adds `raw.hubspot_deals.original_traffic_source` |
| 4 | `db/07_gtm_campaigns.sql` | `raw.hubspot_gtm_campaigns` and its contact/deal association tables |

Two SQL files are **not** migrations and are applied by Docker on first
initialization of the volume (or manually with `psql`): `db/init.sql` creates the
`raw` schema, and `db/02_hubspot_raw.sql` creates the contact/company landing
tables.

Migrations `05`, `08`–`12` were deleted with the deal-source backfill,
brand-inbound recovery, and automation-twin components. They are no longer
referenced.

## Behavior

The runner holds a PostgreSQL advisory lock, runs the plan in one transaction,
and records each filename and SHA-256 checksum in
`analytics.schema_migrations` — the only object it creates outside the `raw`
schema, and it creates that table itself.

A repeat run verifies the checksums and skips completed files. It stops on a
missing file, a SQL error, or a checksum change rather than guessing whether
changed migration history is safe. Every migration uses idempotent DDL
(`IF NOT EXISTS`), which the test suite enforces.

This command changes only the local PostgreSQL schema and migration ledger. It
does not call HubSpot, append snapshots, or change CRM records.

## Schema readiness

Extractors fail closed before their first HubSpot request when the local schema
is stale:

- `extract/extract_deals.py` checks the required `raw.hubspot_deals` columns.
- `extract/extract_gtm_campaigns.py` checks the three GTM raw tables.

Both print the migration command on failure.

## Live deal extraction

After migrations, run the read-only extraction from the repository root with the
confirmed property mapping:

```bash
HUBSPOT_DEAL_NEXT_STEP_DATE_PROPERTY='' \
HUBSPOT_DEAL_PRODUCT_SERVICE_PROPERTY='product_s_' \
HUBSPOT_DEAL_BILLING_MODEL_PROPERTY='billing_model' \
python extract/extract_deals.py
```

This requires `HUBSPOT_PRIVATE_APP_TOKEN` and `DATABASE_URL`. It reads HubSpot
deals and associations and appends warehouse snapshots; it does not write to
HubSpot. The empty next-step-date setting is intentional — the portal review
found no distinct next-step date property.
