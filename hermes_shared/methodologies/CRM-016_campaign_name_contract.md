# CRM-016 — Campaign-name contract audit

Read-only. No workflow, contact, deal, campaign, field or association change.
Match status is derived by **exact string equality only** — no casing,
normalisation, or fuzzy matching. No source value was reverse-inferred from a
campaign association. `execution_authorized` is false.

> The final control instruction arrived truncated as "Do not reverse-infer". It
> is read as *do not reverse-infer source values from associations*, consistent
> with CRM-015-B5. Association evidence appears only as corroboration and never
> as the basis for a proposed value.

## The headline: the naming contract is mostly healthy

Of **218 contacts** carrying a `Latest Campaign Source`, **211 (96.8%) match a
canonical GTM Campaign name exactly.** Drift is confined to 3 literals covering
7 contacts.

This **corrects CRM-015**, which is the most important output of this audit.

## Corrections to CRM-015

**CRM-015-B2 was scoped too broadly.** It stated that the only two stamped values
in existence match no campaign name. That was true of *deals created since
2026-07-01*, but not of the data as a whole. Across all contacts there are six
distinct literals, three of which match exactly and cover 211 of 218 contacts.

**CRM-015-B3 is substantially weakened.** It hypothesised that association
failures occur because no stamped name ever matches a campaign. But 190 contacts
carry an exactly matching BlackHat literal, so a name-matching step *would*
resolve for them. That hypothesis cannot explain the BlackHat association
failures and is superseded below.

Campaign naming is therefore **not** the primary cause of the attribution failure.

## What is actually broken

**The copy step, not the stamp.** Of the same 218 contacts:

| Primary Campaign Source holds | Contacts |
|---|---|
| Nothing (blank) | 201 |
| A data-enrichment vendor name | 14 |
| An actual campaign value | 3 |

The stamp lands correctly and then **fails to propagate**. That copy is precisely
what workflow `1833911074` performs, and precisely what was repaired on
2026-08-11 — so the CRM-014 fix targets the right step.

**A second writer occupies the same field.** 1,591 contacts hold enrichment
vendor names in `Primary Campaign Source`:

| Value | Contacts |
|---|---|
| Apollo | 1,441 |
| Findymail | 70 |
| LeadMagic | 28 |
| user managed | 27 |
| Prospeo | 16 |
| Icypeas | 9 |

Contact `239815031112` shows the collision directly: `Primary Campaign Source` =
`Apollo` while `Latest Campaign Source` holds a valid canonical campaign. A
writer with incompatible semantics can overwrite campaign attribution *after* the
repaired workflow writes it. **This is the strongest reason to doubt that the
CRM-014 fix will hold**, and it should be checked before the fix is judged.

The writer was not identified; attribution to an enrichment integration is
inferred from value semantics, not observed.

## The four targeted investigations

| Case | Verdict |
|---|---|
| `Apex: Demo vs PLG — Q3 2026` vs `Demo vs PLG` | No match. Mapping **plausible** — both deals carrying the literal are associated to `59730804023` — but not asserted. |
| `Q326 - Apex Free Scan` vs `Q326 - Apex Free Exploitability Review` | No match. Mapping **contested**: deal `63181945615` associates to the Review campaign, but deal `63621024606` carrying the *same* literal associates to `CloudSec List`. The literal maps to two campaigns. |
| Deal `63621024606` | **Confirmed conflict.** Source literal says Apex Free Scan; association says CloudSec List. One is wrong; the evidence does not say which. |
| Deal `63519644983` | **Confirmed no upstream evidence.** Contact `240124396947` has both campaign fields blank. Populating from the association would reverse the direction of evidence — declined. |

The two mapping cases are **not equivalent** and must not be approved together.

## Campaign coverage

Only 3 of 8 campaigns are referenced by an exact source literal. `CloudSec List`,
`Demo vs PLG` and `Q326 - Apex Free Exploitability Review` appear **only as deal
associations, never as a stamped value** — so association and source disagree by
construction. `Q326 - Sagetap` and the test campaign have no observed traffic.

`FHIR Security Readiness — Q3/Q4 2026` is stamped on one contact but **no campaign
record exists** for it. That contact is `E2E Test 2`, a test record.

## What could not be collected

Requirement 1 — every literal an active workflow writes — is **not satisfied**.
Workflow definitions are unreadable without Chrome MCP, so 13 of 16 crosswalk rows
carry no writer attribution. The three attributed rows rest on the recorded
CRM-014 change to workflow `1833911074`, not on a definition read. Until the
writers are enumerated, this audit describes *what is in the fields*, not
*everything that writes them*.

## Recommended order

1. **Identify the writer putting vendor names into `Primary Campaign Source`.**
   Until it is stopped, any fix to the campaign path can be overwritten.
2. Re-check whether the repaired workflow now populates the field for newly
   stamped contacts — the 201 blank records are the baseline to measure against.
3. Decide the canonical mapping for the two drifted literals, separately.
4. Resolve deal `63621024606` by human decision.

No value is proposed for write. Every crosswalk row is marked
`REQUIRES_HUMAN_DECISION`, `NOT_A_CAMPAIGN`, or already canonical.
