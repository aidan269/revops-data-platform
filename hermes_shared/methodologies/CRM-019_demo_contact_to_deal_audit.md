# CRM-019 — Demo details: contact-to-deal forward sync audit

Read-only and design-only. No workflow, form, property, contact, deal or
association was created, edited, activated, tested, enrolled or replayed. No
warehouse migration or rebuild was run or requested. `execution_authorized: false`.

## Data availability (objective 8, checked first)

Everything needed was present in the current HubSpot snapshot and read read-only:
contact conversion lineage via `recent_conversion_event_name` and
`recent_conversion_date`, the scoping values themselves, and the deal-side
destinations. **No migration was needed and none was run.**

Not available without Chrome MCP, which is not connected: form field-to-property
mappings, workflow definitions, enrollment criteria, and property history.

## The form that matters is not the one named "demo"

The **Web2 Demo Form** drives 81 most-recent conversions, but only **7 contacts**
hold `web2_form_application_name` — and all eleven `web2_form_*` properties have
**no deal-side equivalent at all**. The demo form does not appear to write that set.

The substantive intake is the **Web3 Scoping Form**: 135 submissions, 109 most
recent conversions, and **109 contacts holding a code repo** — an exact match to
its conversion count. That is where contact detail exists and where a deal
destination (`repo_uri`, 1,686 populated) also exists. The audit follows it.

## Forward failure rate — observation

Window: deals created 2026-05-01 to 2026-08-12 whose associated contact holds
`web3_scoping_form__code_repo`. **37 contact-deal pairs.**

| Observed | Pairs |
|---|---|
| Deal `repo_uri` blank | 25 |
| Deal `repo_uri` holds a **different, more specific** value | 10 |
| Deal `repo_uri` exactly equals the contact value | 2 |

Three of the 25 blanks are `zzdummy` test records. **Genuine forward failures: 22.**

## Interpretation — kept separate

**The 10 differing deals are not failures.** Their values are per-engagement — a
PR, a commit, a diff — against a contact value that is a scoping document or bare
repo. The deal field holds the *better* data. A forward copy that overwrote them
would destroy correct detail. That is the single most important design constraint
here, and it inverts the naive reading of "the deal field is wrong".

## Mechanism

**Confirmed:**

1. **Multi-deal ambiguity.** 49 of 109 code-repo contacts have deals, producing
   83 pairs. Contact `101849163786` carries 6+ deals, each a distinct repo;
   `55246214682` has 3 in the window alone. A contact-level field has **no single
   unambiguous target deal** for these.
2. **Deal creation precedes submission.** Deal `22549170096` was created
   2024-09-23 against a submission on 2026-07-16 — nearly two years earlier. Any
   deal-creation-triggered workflow can never carry form data for that population.
   This is the same structural defect CRM-017 found on workflow `1833911074`.
3. **Some source values are not machine-mappable.** Contacts `237361421151` and
   `76202803478` hold free-text prose and multi-repo blocks. No correct workflow
   could safely write those into a URI field.

**Leading but unconfirmed:** that **no copy-to-deal action exists at all**. The
write pattern fits, and deal-side fields look maintained by a separate engagement
process — but workflow definitions are unreadable, so this is not confirmed.

**Not evaluable:** enrollment filters, re-enrollment settings, and conditional
branches. Recorded as unevaluated, not as excluded.

## Proposed forward-only workflow contract

Design only. Nothing below is authorized to be built or activated.

**Trigger** — contact property `web3_scoping_form__code_repo` becomes known.
Never deal creation; that is the defect being designed around.

**Validation gate** — proceed only if the value matches a single-URL shape
(one `https://` token, no whitespace-separated second URL, no newline). Prose and
multi-repo blocks are rejected and logged, never written.

**Eligible sources** — contacts whose `recent_conversion_event_name` resolves to
the Web3 Scoping Form. Excluded: any email on internal domains, any repo value
matching a test pattern such as `zzdummy`, and contacts flagged spam.

**Deal selection** — the hard part, and the rule must fail closed:

> **Corrected by the Chrome-verification addendum below.** The "exactly one deal"
> rule stated here is **withdrawn as unsafe**. Retained for the audit trail; use
> the corrected contract at the end of this document.

| Contact's deal count | Behaviour |
|---|---|
| Zero | Do nothing. Never create a deal. Log as unresolved. |
| Exactly one, `repo_uri` empty | ~~Write.~~ **Withdrawn — see addendum.** |
| Exactly one, `repo_uri` populated | **Do nothing.** Log a conflict for human review. |
| More than one | **Do nothing.** Log for human review — no heuristic picks the target. |

Optionally narrow "more than one" to a single deal created within 24 hours of the
submission, but only if a human approves that rule after seeing its counts.

**Conflict handling** — never overwrite a populated `repo_uri`. The audit shows
populated deal values are usually better than the contact value.

**Re-enrollment** — on, so a later submission can populate a deal that did not yet
exist. Guarded by the empty-destination rule, which makes repeats idempotent: once
written, the destination is populated and the workflow declines to act again.

**Timing** — no fixed delay. The trigger is the value becoming known, so the
source already exists. Deal association may lag; re-enrollment covers that rather
than a race-prone delay.

**Monitoring** — count writes performed, conflicts skipped, multi-deal skips,
validation rejections, and zero-deal contacts, per week. A sustained rise in
multi-deal skips means the selection rule needs revisiting.

**Rollback** — because the workflow only ever writes into an empty field, rollback
is to clear `repo_uri` on exactly the deals it wrote, identified from the write
log. No prior value is ever lost, so no restore is needed.

## ~~Test cohort for later approval~~ — reclassified, see addendum

> **Reclassified as historical remediation-review candidates.** These were selected
> on single-deal plus same-day heuristics, which the corrected contract rejects as
> insufficient evidence of linkage. **They are not a valid forward test cohort**,
> and their execution is neither approved nor proposed.

Five exact records, each a single-deal contact, same-day submission, clean single
URL, blank destination:

| Contact | Deal | Value to write into `repo_uri` |
|---|---|---|
| `133860101702` | `62646799394` | `https://github.com/zircuit-labs/zkr-yield-aggregator` |
| `217340748564` | `62634912363` | `https://github.com/aragon/capital-router` |
| `235477174052` | `62672172124` | `https://github.com/tread-labs-public/tread-token` |
| `185166577485` | `63272092727` | `https://github.com/swaap-labs/swaap-v3-audit` |
| `182459988768` | `63723228433` | `https://github.com/EverlongLabs/blockend/` |

Requires human approval of the exact contact, deal, field and value before
anything runs.

## Backfill

**None proposed**, per instruction, until the forward design is agreed. Historical
analysis is reported as counts only. Any future backfill would additionally need
verified contact evidence, a single unambiguous target deal, and confirmed
equality of source and destination field definitions — a condition most of the
109 contacts fail today.

## Blocking questions before build

1. Which contact property does the live form actually write — `web3_scoping_form__code_repo`
   or the duplicate `web3_scoping_form__code_repository`?
2. Is `repo_uri` the canonical destination? It holds 1,686 values against
   `github_repo`'s 76.
3. Does any workflow already attempt this write?

*All three are answered in the addendum below.*

---

# Chrome-verification addendum — 2026-08-11

Read-only. Recorded from operator Chrome inspection; reported, not independently
confirmed by Hermes. No HubSpot change is authorized. `execution_authorized: false`.

Prior observations are preserved above; corrections are stated explicitly rather
than replacing them.

## The three blocking questions, answered

**1. Source property — resolved.** The Web3 Scoping Form
(`11156c9b-7e9c-4953-9313-68ba035ac031`) connects its live **Code repository**
field to `web3_scoping_form__code_repo` (label *Web3 Scoping Form - Code repo*),
type **multi-line text**, and the field is **not required**. The duplicate
`web3_scoping_form__code_repository` remains unexplained and needs governance review.

*The multi-line type matters:* it is exactly why free-text prose and multi-repo
blocks reach this field, which the source-validation rule must reject.

**2. Destination — resolved.**

| Property | Populated | Dependencies | Classification |
|---|---|---|---|
| `repo_uri` | 1,686 / 5,404 | 5 (only workflow: `Sales > CS: Next Steps`, `590100350`, **OFF**) | **De facto canonical** |
| `github_repo` | 76 / 5,404 | 0 | **Legacy / orphan candidate** |

`github_repo` requires a separate governance review. **Do not archive or modify it.**

**3. Does any workflow attempt the write? — No. `CRM-019-R01` is now CONFIRMED.**
Property usage shows `web3_scoping_form__code_repo` is used in exactly **two
assets — one form and one email — and zero workflows**, and the form reports
**zero directly attached workflows**. Nothing propagates the source to a deal.
The earlier caveat that this could not be confirmed is resolved.

## Correction: the "exactly one deal" rule is withdrawn

My proposed contract allowed a write when a contact had exactly one associated
deal and an empty destination. **That was unsafe and is withdrawn.**

A single associated deal can be unrelated to the scoping request, or substantially
older than it. This audit's own evidence shows deals predating submissions by up
to two years — so **deal count is not evidence of linkage**, and same-day timing
is correlation, not a link. I should not have treated a count as a relationship.

## Corrected forward-only contract

**A write requires a deterministic link between the specific form submission and
the destination deal.** Acceptable mechanisms:

1. the deal is created by the same controlled automation;
2. the deal carries a purpose-built association label for that request; or
3. both records share a unique scoping-request identifier.

**Absent one of these, perform no write and route to an exception queue.** None of
the three exists today, so no write is currently possible by design — building the
linkage mechanism is the prerequisite, not the workflow.

| Element | Rule |
|---|---|
| Trigger | Web3 Scoping Form submission, or an equivalently specific request event |
| Source validation | Exactly one permitted repository URL |
| Destination | `repo_uri` only, and only when blank |
| Overwrite | Never |
| Re-enrollment | Yes, for subsequent genuine submissions |
| No-write exceptions | Zero target, ambiguous target, multi-URL source, populated destination |
| Deal selection | Deterministic linkage only — deal count never suffices |

## The five records are no longer a test cohort

They were chosen on single-deal plus same-day heuristics, which the corrected
contract rejects. They are reclassified as **historical remediation-review
candidates**. Their execution is neither approved nor proposed here, and they must
not be used to validate a forward design.

## What did not change

The 37-pair window still splits 25 blank / 10 more-specific / 2 exact, with **22
genuine forward failures**. The 10 more-specific deals are still not failures and
must never be overwritten. Multi-deal ambiguity and deal-before-submission timing
remain confirmed causes.
