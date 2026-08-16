# Local database migrations

Run the ordered migration runner before a live HubSpot deal extraction:

```bash
.venv/bin/python scripts/run_db_migrations.py
```

The runner applies `db/03_hubspot_deals.sql`, `db/04_hubspot_campaigns.sql`,
and `db/05_deal_source_migration.sql` in that order. It holds a PostgreSQL
advisory lock, runs the plan in one transaction, and records each filename and
SHA-256 checksum in `analytics.schema_migrations`. A repeat run verifies the
checksums and skips completed files. It stops on a missing file, SQL error, or
checksum change rather than guessing whether changed migration history is safe.

This command changes only the local PostgreSQL schema and migration ledger. It
does not call HubSpot, append deal snapshots, run dbt, or change CRM records.

The live deal extractor also checks the required `raw.hubspot_deals` columns
before its first HubSpot request. A stale schema fails closed and prints the
migration command.

After a separately approved migration, run the read-only extraction from the
repository root with the confirmed CRM-005 property mapping:

```bash
HUBSPOT_DEAL_NEXT_STEP_DATE_PROPERTY='' HUBSPOT_DEAL_PRODUCT_SERVICE_PROPERTY='product_s_' HUBSPOT_DEAL_BILLING_MODEL_PROPERTY='billing_model' .venv/bin/python extract/extract_deals.py
```

This requires `HUBSPOT_PRIVATE_APP_TOKEN` and `DATABASE_URL` in the environment.
It reads HubSpot deals and associations and appends warehouse snapshots; it
does not write to HubSpot. An empty next-step-date setting is intentional
because the R3 portal review found no distinct next-step date property.

Rebuild CRM-004 only after that extraction succeeds:

```bash
.venv/bin/dbt build --project-dir transform --profiles-dir transform --select +int_won_accounts +mart_active_pipeline_hygiene_live
```

This reads the local warehouse and rebuilds the selected dbt lineage. It does
not call or modify HubSpot. `+int_won_accounts` is explicit because the
won-account regression test references both that model and `dim_deal`; selecting
only the hygiene lineage can otherwise select the test without materializing
its second parent.
