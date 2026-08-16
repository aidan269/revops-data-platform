# Series A CRM readiness

Use `analytics_analytics.mart_gtm_lifecycle_live` for CRM and investor-facing
analysis. It excludes development fixtures by requiring a deal to have appeared
in a live HubSpot extraction during the last seven days.

## Current operating baseline

- Deal Source taxonomy is active at the deal level.
- 621 live, previously blank deals were safely tagged and an audit CSV was
  produced locally.
- All remaining blank Deal Source values are intentionally left untouched until
  there is evidence strong enough to support an attribution rule.
- Hermes has read-only access to the warehouse; HubSpot record changes remain
  an explicit Codex-approved action.

## Next control points

1. Run the live contacts/companies extraction routinely. It now ingests current
   contact-to-company associations as well as company records.
2. Use the live lifecycle mart—not the legacy all-records mart—for all KPIs.
3. Define a required-field rule by deal stage for Amount, Deal Source, Company,
   and primary contact before pipeline reporting is presented externally.
