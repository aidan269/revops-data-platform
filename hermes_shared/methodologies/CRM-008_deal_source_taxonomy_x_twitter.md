# CRM-008 — Deal Source taxonomy evaluation: `X / Twitter`

Read-only evaluation of one proposed taxonomy addition. This document authorizes
no CRM change, no writeback, and no change to the existing approved mapping.

Evidence source: `analytics_analytics.mart_gtm_lifecycle_live`, live snapshot
extracted 2026-08-09 03:16:28 UTC (5,388 live deals). Hermes read-only only.

## Why the current approved mapping cannot classify X / Twitter

The approved first-touch-to-Deal-Source mapping, as implemented in
`mart_deal_source_backfill_audit`, contains exactly four rules:

| First-touch channel | Approved Deal Source |
|---|---|
| Google Ads | Paid Search |
| Direct, Webflow / Cantina | Website / Direct |
| Email / In-app | Email / Nurture |
| Organic Search | Organic Search |

`X / Twitter` appears in none of them. The consequence is not that the evidence
is weak — it is that the mapping has no entry to resolve to. These 412 deals
carry `utm_quality = 'clean'` and `attribution_evidence_status =
'first_touch_utm'`, which is the strongest evidence tier the warehouse produces.
They are blocked by a **taxonomy gap, not an evidence gap**.

This is why the CRM-008 candidate set is non-empty while the approved-mapping
backfill candidate set is exactly zero: the 621-deal historical writeback already
consumed every deal the four approved rules could deterministically cover. No
further deal can be classified without either a new taxonomy entry or weaker
evidence standards. Lowering the evidence standard is explicitly out of scope.

## Selection rule for the candidate CSV

A deal enters the candidate CSV only when **all four** conditions hold:

1. `hubspot_deal_source` is null or empty after trimming — blank only.
2. `utm_quality = 'clean'`.
3. `first_touch_channel = 'X / Twitter'`.
4. `first_touch_utm_source` is exactly `x` or `Twitter`.

Closed-won and active-pipeline populations are carried in the same file and
separated by the `population` column. They are never aggregated.

## Proposed normalization rule

    'x'  -> 'X / Twitter'
    'Twitter' -> 'X / Twitter'

Exact string match only. No case folding, no prefix matching, no domain parsing.

The live snapshot contains five raw `utm_source` variants on this channel:
`Twitter` (274), `x` (138), `twitter.com` (2), `twitter` (1), `t.co` (1). The
rule as proposed covers the first two. The remaining four records are **not**
silently folded in — extending the rule to a lowercase variant, a domain, or a
link-shortener host is a separate human decision and is listed as an exception.

## Exceptions — not classified

**Corrupted channel with clean quality (8 active records).** These carry
`utm_quality = 'clean'` alongside `first_touch_channel = 'Unknown (corrupted
UTM)'`. The contradiction resolves on inspection: the raw values are `test`,
`test3`, `test7`, `test8`, and `source-test`. They are syntactically well formed,
which is all `utm_quality` asserts, but they are QA traffic and carry no
marketing meaning. All eight have a null CRM deal amount and no associated
company. **Disposition: do not classify.** They are not evidence for any channel
and must not enter any backfill.

**Unnormalized UTM variants (4 records).** `twitter.com` (2), `twitter` (1),
`t.co` (1). Clean evidence, but outside the two literal inputs of the proposed
rule. **Disposition: requires a normalization decision** before inclusion.

## Guardrails

- CRM deal amount is HubSpot `amount`. It is **not ARR and not recognized
  revenue**, and no revenue claim is made from it. All 20 closed-won candidates
  are `customer_motion = 'unclassified'`, so none can support an ARR claim
  regardless of the taxonomy decision.
- Approving the taxonomy addition does **not** approve a writeback. Populating
  any deal requires a separate, exact-record proposal with its own approval.
- The existing approved mapping and source taxonomy are unmodified.
