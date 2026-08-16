# CRM-015 — Deterministic pilot backfill for missed campaign attribution

Read-only. No contact, deal, campaign, workflow, association or Zapier change.
The repaired workflow 1833911074 was not enrolled, tested or replayed.
`execution_authorized` is false. A candidate packet is not approval.

## Result: zero qualifying candidates

The pilot asked for up to 10 highest-confidence candidates. **None qualify**, and
no candidate was manufactured to fill the quota.

This is not a null result for lack of looking. Every deal created on or after
2026-07-01 was evaluated (246 deals), and the population partitions cleanly:

| Population | Deals |
|---|---|
| No associated contact at all | 87 |
| Has contacts, none carrying a campaign stamp | 155 |
| Has a contact with `Latest Campaign Source` populated | 4 |
| **Total in window** | **246** |

All 4 deals in the last row are **already attributed** — their deal-level
`Primary Campaign Source` already equals the contact's stamp. There is nothing to
backfill.

## Two findings that matter more than the pilot would have

**The historical population cannot be recovered by this rule at all.** For 242 of
246 deals the upstream evidence does not exist: 87 have no contact, and 155 have
contacts with an empty `Latest Campaign Source`. Any backfill keyed on that field
has no input. This sharpens what CRM-014 recorded: the workflow fix is forward-only
not merely because it was applied late, but because the historical deals have no
recoverable source evidence.

> **Corrected by CRM-016 (2026-08-11).** The paragraph below overstates its
> scope, and the root-cause hypothesis further down is superseded. Across the
> full contact population there are six distinct `Latest Campaign Source`
> literals, and three of them match canonical campaign names **exactly**,
> covering 211 of 218 stamped contacts. Drift is confined to 3 literals and 7
> contacts. The real failure is the copy from `Latest` into `Primary Campaign
> Source`, plus a competing non-campaign writer. See
> `CRM-016_campaign_name_contract.md`. The zero-candidate result below is
> unaffected.

**The exact-match criterion fails universally** *(within this task's deal window
— see the correction above)*. Only two campaign-source values appear on deals in
this window, and neither matches any of the 8 GTM Campaign names:

| Stamped value | Nearest GTM Campaign | Exact match |
|---|---|---|
| `Apex: Demo vs PLG — Q3 2026` | `Demo vs PLG` | No |
| `Q326 - Apex Free Scan` | `Q326 - Apex Free Exploitability Review` | No |

Campaign Source is free text that has drifted from the campaign object. No
fuzzy or partial matching was used to bridge this — doing so would invent
attribution the evidence does not support.

## A candidate root cause for the CRM-014 association failures — SUPERSEDED

> **Superseded by CRM-016-F1 and CRM-016-F2.** 190 contacts carry an exactly
> matching BlackHat literal, so a name-matching association step would resolve
> for them. The hypothesis below cannot explain the BlackHat association
> failures. Retained for the audit trail; do not act on it.

If the repaired workflow's final step resolves a *Sourced* GTM Campaign
association by matching the stamped name against a campaign record, and **no
stamped value matches any campaign name**, then that step has nothing to resolve.
That is consistent with the missing-target association failures recorded in
CRM-014, and it would mean the applied fix produces attribution values but still
no associations.

This is a hypothesis consistent with the observed data, not a confirmed
mechanism — the workflow's matching logic was not readable. It is the single most
valuable next read-only check.

## Two records needing a human decision

- **Deal `63621024606`** asserts two different campaigns: a stamped source of
  `Q326 - Apex Free Scan` against a `CloudSec List` association. One is wrong.
- **Deal `63519644983`** carries a `Demo vs PLG` association with a blank
  Primary Campaign Source and no contact stamp. A backfill keyed on the
  association would populate it, but that reverses the intended direction of
  evidence — contact stamp drives deal value, not the other way round. Deliberately
  not proposed.

## Criterion that could not be evaluated as written

The rule requires *exactly one contact associated under the **Deal Source**
label*. The HubSpot MCP query layer supports association **existence** checks
only; association labels are not exposed. "Exactly one associated contact" was
used as a strict superset instead.

This substitution does not change the outcome — candidacy already fails on
evidence absence and match failure, both upstream of the label question — but any
future run that finds candidates **must** confirm the Deal Source label in the
browser before proposing a write. The same limit prevents confirming whether the
5 existing campaign associations carry the `Sourced` label.

## What would have been proposed per candidate

Recorded so the shape is fixed before any candidate exists: write the matched
campaign name to the **contact's** `Primary Campaign Source`, let the unchanged
deal property sync propagate it to the deal, then create the `Sourced` GTM
Campaign association. Rollback is to clear the contact field to blank — not to a
guessed prior value — and remove the created association.

## Recommended sequence

1. Read-only: confirm whether the workflow's association step matches on campaign
   name, which would confirm or kill the root-cause hypothesis above.
2. Decide whether Campaign Source should remain free text or become a validated
   reference to the campaign object. Until this is settled, no name-matching
   backfill can be specified.
3. Resolve the two conflicting records by human decision.
4. Only then reconsider a pilot, on deals created after the naming decision.

No backfill of the 242 historical deals is proposed, and none should be attempted
by inference. A blank field remains more honest than a fabricated one.
