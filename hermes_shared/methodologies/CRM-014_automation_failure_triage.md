# CRM-014 — Automation failure triage

Read-only. No HubSpot, form, workflow, Zap, connected-account or CRM change. No
replay, test-run, enrollment, submission, toggle, publish, archive, clone or
repair. Zapier Autoreplay was not enabled or modified and no held run was
replayed, deleted or bulk-selected.

Builds on the CRM-013 form baseline (111 forms) and connects it to HubSpot
workflow failures and Zapier execution failures.

## Collection constraint, and how it was worked around

Chrome MCP is not connected, so the HubSpot automation-health view, workflow
definitions, and the Zapier Zap and run history were all unreachable — the same
blocker recorded in CRM-013.

Rather than record the supplied browser evidence as unverifiable, this triage
verified workflow behaviour **indirectly, through the CRM state those workflows
are supposed to write**. If a workflow's job is to populate a field, the
population rate of that field is observable even when the workflow is not.

That converted 6 of 9 reported failure instances from assertion into corroborated
observation. The remaining 3 stay marked `user_reported_unverified`.

| Reported failure | Verification route | Result |
|---|---|---|
| Set Deal Primary Campaign Source — 4 property updates failed | Population rate of `primary_campaign_source` | **Corroborated** |
| BlackHat Event — 5 association failures, missing property values | Read the campaign record's properties | **Corroborated** |
| Deal Move to Discovery — 2 actions, no target record | Count Discovery deals lacking a contact association | **Corroborated** |
| Channel Leads > New Deal — 9 notifications, recipient not a portal user | Owner directory active/inactive split | **Corroborated** |
| Rippling Email — bounce, non-marketing, unsubscribe failures | Contact marketable-status and opt-out distribution | **Corroborated as expected behaviour** |
| Clarion sequence — bounced address | Contact opt-out counts | **Corroborated as expected behaviour** |
| BlackHat Event — 1 association failure, missing target record | — | Unverified |
| Clarion sequence — invalid enrollment input | Sequences not exposed by MCP | Unverified |
| Content Form Workflow — lifecycle blocked forward-only | — | Unverified, but documented product behaviour |

## The P0

One P0 was assigned, on observed evidence rather than capability.

**Campaign attribution is not reaching deals.** Of 246 deals created since the
GTM campaign object went live on 2026-07-01, **242 carry `primary_campaign_source`
= "Unassigned"** and only 4 carry a real campaign value. The consequence is
measurable on the live event: `Q326 - BlackHat - Event` (59730364830) records a
**65,000 budget, 190 members and 2 opportunities against 0 influenced pipeline**,
and no BlackHat value appears in any deal's campaign source.

The all-time figure (5,400 of 5,404 deals null) was deliberately **not** used as
the basis, because most deals predate the campaign object and their blankness
proves nothing. Restricting to the window where the object exists is what makes
this a current break rather than a historical artifact.

What remains unproven is the mechanism: whether "Unassigned" is written by the
workflow as a fallback or is a field default could not be determined. That
distinction is recorded as inference, not observation, and it matters — a
fallback write would mean the automation reports success while losing attribution.

## Severity discipline

`P0` requires observed loss, corruption or misrouting of revenue-critical CRM
data. It was **not** assigned for a workflow merely being able to write CRM data.
Four findings that touch revenue-critical fields were held at P1 because the
observed evidence showed a failed or absent action without demonstrated data loss.

Two findings were classified **expected behaviour, not breaks**: email
eligibility suppression (91.4% of the 88,934 contacts are non-marketing, 46 are
unsubscribed) and the forward-only lifecycle-stage block. Both appear in
HubSpot's issue list but are designed protective behaviour. Their real cost is
that they crowd the automation-health view and mask genuine failures.

| Severity | Count |
|---|---|
| P0 | 1 |
| P1 | 4 |
| P2 | 3 |
| P3 | 3 |

## Validation outcomes, including what failed

Three required validations **could not be satisfied**, and are recorded as failed
rather than quietly relaxed:

- **Reconcile all 15 HubSpot issue categories** — 12 enumerated, **3 unaccounted
  for**. The automation-health view was unreachable. One fifth of the known issue
  surface is unexamined and cannot be assumed benign.
- **Reconcile the Zapier held-run count** — 32 reported, **0 captured**. Whether
  the 31→32 move is a new hold or a recount is undetermined.
- **Validate every dependency-edge endpoint** — all 6 form-side endpoints validate
  against the CRM-013 inventory; **no target endpoint validates**, because no
  workflow or Zap inventory exists to validate against.

The held-run file is emitted as a `collection_status` record with
`baseline_established: false`, explicitly not as a run inventory. Its single row
documents the gap; it contains no fabricated run rows.

## Cross-links found

23 of the 56 Meetings scheduling links in CRM-013 name a user who is now
inactive, carrying 141 combined submissions — the largest being
`henry-shen/spearbit-introduction-call` at 84. Most last received a booking months
ago, so retirement is the likelier explanation than active breakage, and placement
must be confirmed before treating any as live. The same deactivated-owner
population (45 of 81 owners) is the probable substrate for the notification
failures in `Channel Leads > New Deal`. CRM-007 covers owner-directory resolution
and should be linked to any remediation.

## Remediation

None authorized. Every finding carries `repair_requires_approval = yes` and a
proposed **read-only** next check. Any repair must become a separate proposal
naming exact assets, configuration, records and fields, with rollback and human
approval.
