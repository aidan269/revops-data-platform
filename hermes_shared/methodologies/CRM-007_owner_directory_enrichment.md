# CRM-007 owner-directory and deal-name enrichment methodology

CRM-007 is a proposed read-only enrichment that would resolve HubSpot owner IDs to
human names and extract the `dealname` property. It is the dependency named in
CRM-006 and in the RevOps `Active` note. It proposes no CRM field value, no
association, and no HubSpot write.

Nothing in CRM-007 is executed. This document and the accompanying scope artifact
exist so the enrichment can be approved or rejected against exact evidence.

## Why this is the next task

The active-pipeline hygiene queue currently holds 332 live rows. 306 carry an
owner ID and 26 carry none. Every owner ID is unresolved: the raw and analytics
schemas contain no owner table and no owner-name column, so usable human-name
coverage is 0 of 306, including 0 of the 26 P0 rows.

Sales Ops cannot route the P0 packet without knowing who each owner ID is, so
CRM-006 — the current top human-review item — is blocked on a data gap rather
than on reviewer capacity. Eighteen distinct owner IDs cover the entire queue,
so resolving eighteen records unblocks review of $6.19M of active pipeline,
$3.32M of it in P0.

Ownership is concentrated. Owner `937010361` holds 12 of the 26 P0 deals and
$2,162,301 of the $3,315,882 P0 amount. Routing correctness for that single
unresolved ID governs most of the P0 value, and a stale or departed-employee
mapping would misroute it.

## Target population

Exactly the 18 owner IDs in
`hermes_shared/artifacts/CRM-007_owner_directory_resolution_scope.csv`, taken from
current rows of `analytics_analytics.mart_active_pipeline_hygiene_live` where
`deal_owner_id` is not null. The artifact carries per-owner queue counts by
priority and CRM amounts as observed warehouse values.

The 26 queue rows with no owner ID at all are out of scope. Assigning an owner to
an unowned deal is a CRM change and requires its own proposal.

## Proposed read-only operations

1. `GET /crm/v3/owners` — page the HubSpot owners directory and store owner ID,
   first name, last name, email, and archived state in a new `raw.hubspot_owners`
   table, appended with an extraction timestamp like existing raw tables.
2. Add `dealname` to `CORE_DEAL_PROPS` in `extract/extract_deals.py` and add a
   `deal_name` column to `raw.hubspot_deals` through an ordered migration, so the
   next read-only deal extraction populates deal names. Current snapshots carry
   no `dealname` key on any of 17,238 rows, which is why the CRM-006 packet shows
   no deal names.
3. Rebuild the CRM-004 lineage so the hygiene mart exposes `deal_owner_name` and
   `deal_name` as observed joined values.

Both HubSpot operations are `GET` requests. Neither creates, updates, deletes, nor
archives any HubSpot record. Neither is authorized by this document.

## Evidence rules

- Owner names come only from the HubSpot owners directory, joined on exact owner
  ID. No name is inferred from email local parts, deal patterns, or activity.
- An owner ID with no matching directory record stays blank and is reported as
  `unresolved_owner_id_not_in_directory`, which is a manual-review outcome.
- Archived owners are labeled as archived rather than silently dropped, because an
  archived owner on an active P0 deal is itself a routing finding.
- Deal names are stored exactly as returned. A deal with no name stays blank.

## Controls

- `execution_authorized` is false for CRM-007 and for every row in its artifact.
- Approval to run the read-only extraction is separate from approval to change any
  CRM record. Resolving an owner name authorizes no reassignment.
- Any later owner reassignment, deal-name edit, or field update needs its own
  proposal with exact record IDs, exact old and proposed values, revalidation, and
  explicit user approval.
- The extraction is append-only against local raw tables and makes no HubSpot
  modification, so rollback is limited to discarding local rows.
