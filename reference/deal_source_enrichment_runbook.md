# Deal Source enrichment runbook

## Purpose

Preserve the current HubSpot `Deal Source` value in the warehouse before any
historical backfill. The enrichment job must only update records where this
field is blank.

## Refresh sequence

```bash
docker compose exec -T postgres psql -U revops -d revops -f /workspace/db/05_deal_source_migration.sql
python extract/extract_deals.py
cd transform
dbt run --select stg_hubspot_deals dim_deal mart_gtm_lifecycle --profiles-dir .
```

## Safety check

Run this in Hermes before preparing a writeback:

```sql
SELECT
  count(*) AS deals,
  count(*) FILTER (WHERE hubspot_deal_source IS NULL) AS blank_deal_source,
  count(*) FILTER (WHERE hubspot_deal_source IS NOT NULL) AS already_tagged
FROM analytics_analytics.mart_gtm_lifecycle;
```

Never overwrite a nonblank `hubspot_deal_source`. Generate the review file
from blank records only, and retain the modeled first-touch channel alongside
the proposed value as audit evidence.
