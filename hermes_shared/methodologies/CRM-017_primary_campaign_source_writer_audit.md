# CRM-017 — Primary Campaign Source contamination writer audit

Strictly read-only. No HubSpot, workflow, import, contact, association or campaign
property change. No contact file downloaded. `execution_authorized: false`.

## Data source: warehouse unavailable and structurally unable to answer

Two independent reasons, both recorded rather than worked around:

1. The Docker daemon is not running, so no warehouse snapshot was queryable.
2. Even running, the warehouse could not answer this question. `CONTACT_PROPS`
   in `extract_hubspot.py` extracts only `email`, `jobtitle`, `hs_seniority`,
   `createdate` and the UTM fields. **Neither campaign-source property is
   extracted**, and no reference to `campaign_source` exists anywhere in
   `extract/`, `transform/` or `db/`.

A migration was permitted when a required property is missing. It was **not run** —
reading HubSpot directly through the read-only MCP answered the question with no
write of any kind, local or remote.

## Confirming the browser evidence

Contact `239815031112` reads exactly as reported: `primary_campaign_source` =
`Apollo`, record source `IMPORT`, source detail `bhf.csv`, created
`2026-08-04T13:35:18Z` — which is 09:35 EDT.

**`bhf.csv` accounts for exactly 133 contacts, all carrying `Apollo`**, matching
import `78612986`'s reported 133 new contacts precisely.

## The population: 1,591 contacts, fully partitioned

| Value | Contacts | | Record source | Contacts |
|---|---|---|---|---|
| Apollo | 1,441 | | IMPORT | 1,577 |
| Findymail | 70 | | EXTENSION | 7 |
| LeadMagic | 28 | | INTEGRATION | 6 |
| User Managed | 27 | | CRM_UI | 1 |
| Prospeo | 16 | | | |
| Icypeas | 9 | | | |

Both partitions sum to 1,591 with no record unassigned, across 22 distinct named
sources.

## Attribution — observation kept separate from inference

**The critical caveat:** `hs_object_source_*` records how the **record** was
created, not which writer set `primary_campaign_source`. Record creation is
observed; the property write is inferred.

| Classification | Contacts |
|---|---|
| Observably tied to import `78612986` | 133 |
| Tied to an unidentified import | 1,444 |
| Tied to a named integration | 6 |
| Tied to an unnamed browser extension | 7 |
| Manual CRM UI entry | 1 |

Only **one** contact — `239815031112` — has a browser-confirmed property source.
For the other 132 `bhf.csv` records the property write is a strong inference. The
single confirmed import was **not** generalised to the population.

**The 14 contacts import `78612986` updated rather than created cannot be
identified**, because they retain their original creation source. They are queued
for browser review.

A telling pattern: `blackhat2` alone carries five different vendor values (Apollo
78, Findymail 65, LeadMagic 27, Prospeo 16, Icypeas 3). That is the signature of a
list-building export whose email-provenance column was mapped into
`primary_campaign_source` on import. This is inference, not observation.

## Remediation split

- **14 contacts have recoverable campaign evidence** — 13 carry
  `Q326 - BlackHat - Event`, 1 carries `Q226 - HealthSec Boston`, both exact
  canonical matches to their own `Latest Campaign Source`.
- **1,577 have no recoverable evidence** — `Latest Campaign Source` is blank.
  Nothing can be proposed for them without inventing attribution.

No proposed value derives from a campaign association, and no fuzzy match was
used. All 14 remain blocked pending property history, because it is not yet known
whether the vendor value *overwrote* a campaign value or the field was never
campaign-valued — that difference decides whether remediation is a restore or a
first write.

## Objective 7

> **Superseded by the browser-verification addendum below.** Both hypotheses in
> this section were resolved **false** on 2026-08-11. Retained for the audit trail.

**Can the corrected workflow overwrite vendor contamination? — Unresolved, and
the evidence leans toward no.** Three of the 14 recoverable contacts
(`239812707254`, `237948937864`, `239584226226`) were modified at
2026-08-11T20:45Z, after the workflow change was recorded at 20:21Z, and **still
hold `Apollo`** while holding a canonical campaign in `Latest Campaign Source`.
That is suggestive, not conclusive: `lastmodifieddate` moves for any property
change, so it is not proven the workflow touched them.

**Could vendor values block the copy step? — Plausible, but not the main cause.**
CRM-016 found 201 of 218 stamped contacts have a **blank** `primary_campaign_source`
and were still never written. Contamination cannot explain those — there was
nothing to block. If enrolment filters on the field being empty, that would affect
only the 14 recoverable records.

**Are future CSV imports an active recurrence risk? — Confirmed, and
accelerating.** 683 contaminated contacts created in July and **875 in the first
11 days of August**, against 33 across all prior months combined. 97.9% arrived in
the last six weeks. **Any cleanup will be re-contaminated within days unless the
import column mapping changes.** Fix the mapping before cleaning anything.

## Property history unavailable

No property-history surface exists in the available tooling, so the actual writer
of `primary_campaign_source` cannot be established for any contact except the one
confirmed in the browser. Rather than guess, an exact browser-review queue is
recorded in the manifest: the import's 14 updated contacts, property history for
the 14 candidates, the workflow's enrolment and overwrite settings, the 3
post-change contacts, and the 8 records with no source detail.

## Scope note on enumeration

All 1,591 contacts are accounted for at cohort grain across 30 rows. Per-contact
identifiers were materialised only for the 14 remediation candidates — writing
1,591 personal contact records into a repository artifact would sit uneasily with
the control against downloading contact files. The exact filter to reproduce the
full list is recorded in the manifest.

---

# Browser-verification addendum — 2026-08-11

Read-only. Recorded from operator browser inspection; reported, not independently
confirmed by Hermes. No HubSpot record, import, workflow, contact, association or
campaign property was changed. No Docker, migration or warehouse rebuild was run.

## Workflow `1833911074` as saved

| Setting | Observed |
|---|---|
| Status | ON |
| Sequence | Delay 2 minutes → Edit associated contact → Create associations |
| Edit target | Associated Contact under the **Deal Source** label |
| Property | `Primary Campaign Source` |
| Value source | `Latest Campaign Source (Contact: Deal Source, Most recently created)` |
| Change type | **Replace** |
| Enrollment trigger | Deal record created |
| Additional filter | None |
| Re-enrollment | **OFF** |
| Recent action error | No target record was found to run the action on |

## Both overwrite hypotheses are resolved false

**Vendor values do not block the workflow.** The change type is `Replace`, so a
populated field is overwritten, and there is no enrollment filter on the field
being empty. Nothing about contamination prevents the write.

**The three post-change contacts were never touched by this workflow.** Property
history for `239815031112`, `239812707254`, `237948937864` and `239584226226`
shows a **single write each — `Apollo`, from the original import**. Their later
`lastmodifieddate` values came from unrelated record changes. My earlier reading
of those timestamps as evidence about the workflow was wrong; `lastmodifieddate`
was too blunt an instrument, and property history settles it.

| Contact | History | Written by import |
|---|---|---|
| `239815031112` | Apollo only | `78612986` (`bhf.csv`) |
| `239812707254` | Apollo only | `78612986` (`bhf.csv`) |
| `237948937864` | Apollo only | `78257087` (`blackhat2`) |
| `239584226226` | Apollo only | `78545398` (`apollo-contacts-export (4).csv`) |

Two import IDs are newly observed. That mapping holds for these sampled contacts;
extending it to every contact carrying the same source detail stays inference,
since a file can be imported more than once.

## The leading design risk: one-shot timing — `CRM-017-F5` (P1)

The workflow fires **on deal creation**, waits 2 minutes, then edits the
associated Deal Source contact — with **re-enrollment off**. If the Deal Source
association or the contact's `Latest Campaign Source` does not exist inside that
2-minute window, the action has no target and **never runs again for that deal**.
The visible "no target record" error corroborates exactly that.

This is one mechanism that explains three previously separate findings:

- **CRM-015** — 242 of 246 deals unattributed, because most deals never had the
  upstream evidence *at the moment the workflow ran*.
- **CRM-014** — the no-target association failures.
- **CRM-016** — 201 of 218 stamped contacts with a blank Primary Campaign Source:
  the stamp arrived *after* deal creation, and nothing re-ran.

Configuration is observed; the mechanism remains inference, held at medium
confidence.

## What this changes for remediation

Nothing is authorized. `execution_authorized` stays **false**.

The four verified contacts show **no prior campaign value ever existed** on the
property, so remediation for them would be a **first write, not a restore** —
a materially different proposition needing its own approval. The remaining **ten
candidates stay queued**; their histories must not be inferred from these four.

Import recurrence remains a **separate confirmed control failure**, unaffected by
any of this.

## Recommended order, revised

1. **Change the import column mapping.** Still first — everything else is undone
   without it, and it is independent of the workflow problem.
2. **Design the forward attribution workflow** described below. The current
   deal-creation trigger is structurally unable to catch late-arriving campaign
   evidence.
3. Pull property history for the remaining 10 candidates.
4. Only then propose remediation, as a separate approved proposal.

## Recommended next controlled task — design only, do not activate

A **contact-based forward attribution workflow**, triggered when
`Latest Campaign Source` becomes known on a contact rather than on deal creation,
which removes the one-shot race. The design must specify:

- explicit eligibility rules
- conflict handling
- re-enrollment behaviour
- estimated affected-record counts
- rollback method
- a small exact-record test cohort requiring human approval

Design only. Activation is not authorized.
