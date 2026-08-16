# CRM-004 Active Pipeline Hygiene methodology

CRM-004 is a read-only owner-routing proposal built from live-only deal IDs in
mart_gtm_lifecycle_live. Open status comes from the latest pipeline-stage
metadata. No HubSpot action or property value is generated.

## Observable fields

The current warehouse extract exposes amount, created date, close date, Deal
Source, pipeline/stage, deal-level modification timestamp, attribution evidence,
and direct deal-company associations. It does not expose deal owner, next step,
next-step update time, product/service, or billing model. Those four areas are
reported as unavailable_in_warehouse_extract_not_scored rather than missing.
Consequently, CRM-004 makes no stale-next-step claim.

## Gap rules

- Close date: missing; past on an open deal; before deal creation; or more than
  730 days in the future. The latter two are labeled implausible.
- Deal Source: blank only. It remains blank unless an existing approved mapping
  and clean deterministic evidence are both present. This population has zero
  such review candidates.
- Direct company: no row in the latest direct deal-company association model.

No name, deal-title, web, LinkedIn, or company-history inference is used.

## Prioritization

High CRM deal amount is the 75th percentile of positive open-deal amounts:
$60,000. Close-date urgency includes dates within 30 days, past dates, missing
dates, and implausible dates.

1. P0: high amount plus close-date urgency/risk.
2. P1: close-date urgency/risk.
3. P2: high amount without close-date urgency/risk.
4. P3: remaining observable-gap records.

CRM deal amount is neither ARR nor recognized revenue.

## Human workflow

Sales Ops routes each row to the current CRM deal owner because owner data is
unavailable in this extract. Marketing Ops reviews Deal Source evidence. Sales
Ops reviews company associations. No field is populated without exact,
record-scoped evidence and explicit approval. Before any future approved change,
capture the old value or association state; rollback restores only that exact
captured state.
