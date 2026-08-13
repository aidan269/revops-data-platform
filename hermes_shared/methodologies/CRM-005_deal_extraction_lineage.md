# CRM-005 deal extraction readiness and lineage

CRM-005 changes warehouse extraction code only. It does not run a HubSpot
request, migrate the live raw database, or update CRM records.

## R3 schema readiness

The confirmed R3 preflight found that the live extractor's typed deal columns
are defined in `db/03_hubspot_deals.sql`, but that file is not mounted by the
existing Docker initialization path. `scripts/run_db_migrations.py` is now the
required local readiness step. It applies the existing 03, 04, and 05 scripts
in filename order under an advisory lock, records checksums in
`analytics.schema_migrations`, and safely skips verified prior applications.
The extractor fails before any HubSpot request when its required local columns
are absent. Preparing this runner does not authorize or execute a migration.

## Canonical fields

| Canonical field | Default/configured HubSpot internal property |
|---|---|
| deal_owner_id | hubspot_owner_id |
| next_step | hs_next_step |
| next_step_updated_at | HUBSPOT_DEAL_NEXT_STEP_DATE_PROPERTY |
| product_service | product_s_ (confirmed R3 mapping) |
| billing_model | billing_model (confirmed R3 mapping) |

The three environment-configured properties default to disabled because their
portal-specific internal names are not available in the warehouse. Empty
configuration values are never sent to HubSpot. Source nulls remain null.

## Lineage

HubSpot deal properties → extract/extract_deals.py canonical raw JSON keys and
future nullable raw columns → stg_hubspot_deals enforced contract → dim_deal →
mart_gtm_lifecycle → mart_gtm_lifecycle_live →
mart_active_pipeline_hygiene_live → CRM-004 export.

Every new snapshot writes _crm_admin_fields_extracted=true. Historical snapshots
lacking that marker are labeled unavailable_in_current_snapshot_not_scored.
Only a new, separately authorized live extraction can turn those fields into
observable populated/missing/stale states.

Next-step staleness is evaluated only when both next_step and an explicit
next_step_updated_at are available. The threshold is more than 30 days.
