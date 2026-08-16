# CRM-013 — Cantina form-estate read-only baseline

Read-only. No HubSpot write, no workflow or Zap toggle, no form edit, publish,
clone, archive, test-run, replay or submission. No credential, token, webhook
secret or submission payload was accessed or stored.

Requested as **CRM-008**. That ID is occupied by an open, partially-approved Deal
Source taxonomy proposal and its child execution package `CRM-008-EXEC-CW`.
Renumbered to CRM-013 to preserve unique proposal IDs, following the precedent
recorded in the CRM-008 ledger entry, which was itself renumbered from CRM-007.

## Scope, and why it is narrower than requested

The task asked for a complete automation-infrastructure map: HubSpot workflows,
Zapier Zaps, forms, a dependency graph, and reconciliation of HubSpot's
automation-health issues. Collection was to run through Chrome MCP against
signed-in HubSpot and Zapier sessions.

**Chrome MCP is not connected in this session.** `HANDOFF_PROTOCOL.md` §4 places
Chrome MCP outside both Hermes services, which is consistent. The connected
alternatives were probed and cannot substitute:

| Surface | Probe result | Collectable |
|---|---|---|
| HubSpot workflows (161) | No `WORKFLOW` object type in the HubSpot MCP schema | No |
| HubSpot automation health (15 issues) | No automation-health surface exposed | No |
| Zapier Zaps (25) | Zapier MCP exposes only "Zapier Manager", **0 connected accounts** | No |
| Zapier held runs (31) | Not inspectable | No |
| HubSpot forms | `FORM` object readable (`readAccess: AVAILABLE`) | **Yes, partially** |

This baseline therefore covers **forms only**. No workflow, Zap, or dependency-edge
artifact was emitted. Emitting empty ones was rejected deliberately: the stated
purpose of this task is drift detection, and a baseline recording zero workflows
would cause a future run to report "161 workflows appeared" as new infrastructure.

## Source and method

Single source: HubSpot MCP `query_crm_data` over object type `FORM` (`0-28`),
two pages, 111 records, observed `2026-08-11T18:20:00Z`.

`hs_object_id` is blocked as hidden on this object; `hs_form_id` (the form GUID)
is the stable identifier and is used as the primary key throughout.

Fields collected: form GUID, name, `hs_status`, submission count, spam count,
last-submission timestamp, created, updated. Fields **not** available on the
object and recorded as `not_collected`: form type, downstream workflows, downstream
Zaps, CRM properties populated, attribution fields captured, placement/source.

`hubspot_owner_id` is exposed but unpopulated on all 111 records.

## The count reconciliation

The browser reported 49 forms and 6 disabled non-HubSpot forms. The object returns
111. These reconcile exactly:

| Partition | Count | Basis |
|---|---|---|
| HubSpot marketing forms | 49 | marketing (37) + unnamed blank (5) + test (4) + clone (3) |
| Non-HubSpot selector-named capture forms | 6 | matches the 6 reported disabled non-HubSpot forms |
| Meetings scheduling links | 56 | modelled as FORM objects, excluded from the Forms UI list |
| **Total** | **111** | |

The 6 selector-named forms (`.contact_form`, `.css-8atqhb`, `.css-0`,
`.form_form`, `#email-form .form_form`, `#email-form .mockup_form`) hold 204
lifetime submissions and every one stopped receiving submissions between
2025-02-17 and 2025-03-03 — consistent with the reported disabled state. The
identification is inferential, by count and naming pattern; it was not confirmed
against the UI.

**Unreconciled:** observed spam total is **18**, browser reported **19**. The
variance of 1 is recorded as open. `hs_spam_submissions` is null rather than zero
on many records, so nulls may conceal counts, and the UI warning may scope to a
time window or to marketing forms only.

## State partition

`hs_status` is the only state the object exposes, and all 111 records report
`PUBLISHED`. There is no draft, disabled, or archived record in this source.
Disabled state is therefore partitioned by browser report, not object state — and
that disagreement is itself recorded as finding `CRM-013-F011`. Archived state is
not observable at all.

Activity state is derived, not reported: `never_submitted` (45), `stale` (36,
meaning no submission in over 180 days as of the observation date), `active` (30).

## Risk scoring

Applied per the CRM-013 rubric. **No P0 was assigned.** P0 requires evidence that
active automation may silently lose, corrupt, misroute or improperly modify
revenue-critical CRM data — and every path from a form to a CRM write runs through
workflows and Zaps that could not be inspected. Asserting P0 from form-side
evidence alone would be inference, not observation.

| Risk | Count |
|---|---|
| P1 | 13 |
| P2 | 21 |
| P3 | 77 |

Observation and inference are kept in separate columns throughout the failure
register: `detail` carries what was observed, `uncertainty` carries what cannot be
concluded from it. A stale or unused form is **not** recorded as broken.

## What a future run should compare

Primary key `form_id`. Compare `form_name`, `hs_status`, `activity_state`,
`submissions`, `spam_submissions`, `last_submission_utc`, `updated_utc`,
`asset_class`, `risk`. New IDs indicate new infrastructure; missing IDs indicate
deletion; `active → stale` transitions and rising spam share indicate health
regression; `owner` moving off `not_populated` indicates ownership drift.

Baseline version 1 covers forms only. A future run that also collects workflows
and Zaps must treat those as a **new** baseline, not a diff against this one.

## Artifacts

- `hermes_shared/artifacts/CRM-013_forms.csv` — 111 rows, one per form
- `hermes_shared/artifacts/CRM-013_failure_register.csv` — 11 findings
- `hermes_shared/artifacts/CRM-013_manifest.json` — machine-readable manifest, counts, validation, explicit `not_collected` scope
- `hermes_shared/methodologies/CRM-013_form_estate_baseline.md` — this document

## Remediation

None authorized. Any repair must be a separate proposal naming the exact form,
the exact configuration or fields, expected records affected, rollback method, and
human approval. Nothing in this baseline constitutes approval to change anything.
