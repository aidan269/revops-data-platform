# CRM-006 P0 active-pipeline review methodology

CRM-006 is a read-only human review proposal over the 26 rows currently labeled
`P0_high_value_close_risk` in `analytics_analytics.mart_active_pipeline_hygiene_live`.
It does not call HubSpot, propose automatic values, or authorize a CRM change.

## Evidence contract

The packet carries observed warehouse values only: deal ID, deal name when
available, CRM deal amount, stage, close date, owner ID, next step,
product/service, and billing model. Each action is split into an observed-data
statement and a requested human review. Blank fields remain blank and no close
date, next step, source, company, product, billing model, or other value is
inferred.

Deal names are unavailable because current deal snapshots did not extract the
`dealname` property. The artifact states that limitation rather than deriving a
name from another field.

## Owner-name coverage

All 26 P0 rows have a current owner ID. The existing raw and analytics schemas
contain no owner table or owner-name column, so usable human-name coverage is
0 of 26. A separate future read-only enrichment may extract the HubSpot owners
directory and join it by owner ID. That enrichment is not part of CRM-006 and
requires separate approval; names must not be inferred.

## Controls

- `execution_authorized` is false for every row and for the proposal.
- Recommendations request human review only and propose no field value.
- Any later CRM modification requires a separately scoped proposal, exact old
  and proposed values, revalidation, and explicit approval.
