# RevOps transform

This dbt project is the read-only RevOps cleanup workflow. It reads the latest
warehouse extracts and produces reviewable analytics tables; it does not write
to HubSpot.

## Daily workflow

Build the current-deal cleanup outputs:

```bash
dbt build --profiles-dir . --select mart_gtm_lifecycle_live mart_pipeline_health_live mart_deal_cleanup_queue_live
```

Review these tables in priority order:

1. `analytics_analytics.mart_deal_cleanup_queue_live` — deal-level work queue.
   `suggested_deal_source` is populated only for the approved, high-confidence
   first-touch mappings; all other blanks are marked `manual_review_required`.
2. `analytics_analytics.mart_pipeline_health_live` — rollup of missing source,
   company, and primary-contact data by current pipeline stage.

The permanent read-only reconstruction of the 621-deal Deal Source backfill is
`analytics_analytics.mart_deal_source_backfill_audit`. It records each deal's
current Deal Source, first-touch evidence, and the fact that the original
generated audit CSV was removed.

Any CRM change remains a separate, deliberate human action outside this
repository. Re-run the dbt command after the next warehouse extraction to
refresh the queue and confirm the remaining gaps.

## Investor customer-motion reporting

Build the live-only customer-motion foundation with:

```bash
dbt build --profiles-dir . --select +fct_customer_motion_live+
```

The reporting deliberately leaves deals unclassified unless a reviewed seed
override provides defensible product/service and ARR evidence. See
`docs/customer_motion_methodology.md` for output definitions, limitations, and
the evidence Viv needs from Sales, CS, and Finance.

## Web attribution readiness

The read-only web/marketing readiness layer is documented in
`docs/web_attribution_readiness.md`. The exact future tracking requirements are
in `docs/web_tracking_gap_spec.md`; they are specifications only and do not
change the website or CRM.
