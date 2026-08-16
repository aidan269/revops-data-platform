# CRM-020 — Demo & Contact Field Sync

Read-only, design-only. No form, property, workflow, contact, deal, association,
email, list, sequence or enrollment state was changed. Workflow `1865239693` was
treated as superseded and unsafe and was neither modified nor deleted.
`execution_authorized: false`.

## The premise needs correcting first

**Deal creation is not broken.** 74 of 81 demo contacts (91.4%) and 176 of 180
Contact Us contacts (97.8%) already have deals — 112 created in the recent window
alone. The defect is **field quality on deals that already exist**, not absent deals.

## Production forms

| Role | Form | GUID | Subs | Spam | Last submission |
|---|---|---|---|---|---|
| Demo | Web2 Demo Form | `94363e90-…c148` | 123 | 10 | 2026-08-11 |
| Contact Us | Contact Us Form | `fd7f7d47-…c621e` | 351 | 1 | 2026-07-30 |

Rejected: **General Contact Form** (189 subs but nothing since 2025-02-21 — ~18
months stale, legacy not production) and **Contact Us Form - Bounties** (active
but a separate intake path). Website placement could not be captured.

## The actual defect: one path names deals correctly, the other doesn't

| | Demo | Contact Us |
|---|---|---|
| Deals in window | 45 | 67 |
| **Malformed names** | **41 (91%)** | **0 of 11 sampled** |
| Convention | `{service} - {company}` | `{company} - {service}` |
| Blank amount | 45 (100%) | all sampled |
| Closed Lost | 37 (82%) | 60 (90%) |

Demo deals read ` - `, `Apex - `, ` - Geky Tech` — a template firing with one or
both tokens unresolved. Contact Us deals read `CryptoTotem - Spearbit Smart
Contract Security Review`, correctly populated every time.

**The two intake paths use opposite token orders and only one works.** That is the
finding. The fix for Demo is to adopt the convention that already works, not to
invent a third.

## Objective 5 — reconciliation

**Does the described divergence explain the missing deal-level fields? Partly —
and it does not explain deal creation at all.**

`1858050407` is active with visible actions limited to owner assignment, company
copy and a two-minute delay. `1798256771` holds a Create deal action but is **OFF**.
Yet **112 deals were created from these two forms in the window.**

So **a third, unidentified creator is producing these deals.** The divergence is
consistent with poor field quality — create-deal logic carrying naming and fields
sits in a disabled workflow while something simpler actually creates the records —
but creation itself is happening elsewhere.

**No replacement can be safely designed until that creator is identified.** Building
an intake workflow now would add a second creator alongside an unknown first one
and double the deals. The CRM-013 Zap inventory lists `Webflow Form Submission ->
HS` (`285219462`) as a candidate worth checking first.

## Other findings

- **Blank amount is correct, not a gap.** An intake form cannot know deal value.
  Recorded explicitly so it is never auto-populated.
- **82–90% of intake deals are Closed Lost.** Any field repair mostly touches dead
  records, and it is worth asking whether a deal should be created per submission
  at all.
- **Demo detail fields have nowhere to go.** All eleven `web2_form_*` properties
  lack deal-side equivalents, and only 7 contacts hold `web2_form_application_name`
  against 81 demo conversions — so the demo form probably does not even write them.
- **Duplicates exist.** Contact `238604853037` holds `Grandtake - Smart Contract
  Security Review` and `Smart Contract Security Review - Grandtake`, four days
  apart under both conventions.
- **Owner is a de facto default per path**, not routing: 40 of 45 demo deals to one
  owner. Must be stated deliberately in any new design, not inherited by accident.

## Two designed workflows — OFF, not built

Both share: **Sales Pipeline (default)** / **New Lead**; naming
`{company} - {service}`; exclusions for spam, internal domains and test patterns;
re-enrollment **ON** guarded by duplicate prevention; **never write to an existing
deal**; `dealstage`, `hubspot_owner_id` and `amount` treated as curated and never
rewritten.

**`MASTER | Intake | Web2 Demo → Deal`** — trigger: Web2 Demo Form submission.
**`MASTER | Intake | Contact Us → Deal`** — trigger: Contact Us Form submission.

**Unresolved name tokens produce no deal.** If either token is missing, route to an
exception queue rather than emit a partial name — that single rule would have
prevented all 41 malformed demo deals.

**Duplicate prevention:** no deal if the contact already has an open deal from the
same form within 30 days; route to exception.

**Monitoring:** weekly counts of creations, exceptions and unresolved tokens; alert
above 5% unresolved, or on any name beginning or ending with the separator.

**Rollback:** these workflows only ever create; they write nothing onto pre-existing
records. Rollback is deleting only the deals they created, after human confirmation.

## Web3 submission confirmation (objective 9)

- **On-screen confirmation: NOT VERIFIED.** Requires loading the live form. Recorded
  as unverified rather than assumed working.
- **Email receipt: UNDETERMINED.** CRM-019 found the Web3 scoping property is used
  in one form *and one email*, so an email asset already references it — but whether
  that is a submitter receipt or an internal notification is unknown. **Confirm the
  existing email's audience before building anything new**; the requirement may
  already be met.

## Follow-up sequence — documented, not designed

Trigger on a genuine non-excluded submission. Suppress: spam/internal/test, the
91.4% non-marketing population, unsubscribed and hard-bounced addresses, and
anything a human has already replied to. Stop on: reply, meeting booked, deal
leaves New Lead, unsubscribe, or completion. Depends on the intake workflows
landing first, since stop conditions reference deal stage.

## What blocked this audit

**Chrome MCP is not connected.** Objective 2 (live field capture) is **unmet** —
no field label, type or required status was captured for either form. Objective 4
is **partially unmet** — workflow definitions are unreadable, so `1858050407` and
`1798256771` are reconciled only from operator-reported configuration. **Both
crosswalks are provisional on the source side.**

## Prerequisites before any build

1. **Identify the actual creator of intake deals.** Nothing else is safe without it.
2. Capture the live field inventory for both forms.
3. Agree one naming convention across both paths.
4. Agree the owner routing rule with Sales.
5. Decide whether every submission should produce a deal, given 82–90% close lost.
