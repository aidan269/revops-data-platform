# CRM-009 — Closed ARR Deal Source coverage

Read-only. No HubSpot call, no CRM write, no warehouse write.

Snapshot: live extraction `2026-08-10T16:02:37Z`, dbt models rebuilt
`2026-08-10T16:03:39Z`, 5,396 live deals.

## Authoritative definition (Viv)

A deal is in the **closed-ARR population** if and only if:

1. Deal Stage is any Closed Won stage, and
2. `billing_model` equals exactly `Subscription - ARR`.

ARR is never inferred from deal amount, closed-won status, Finance data, or
product/service.

## Why the prior zero-result is superseded

The earlier run returned 0 because `billing_model` was null on all 5,396 deals —
the property was not being requested from HubSpot. A new extraction at
`2026-08-10T16:02:37Z` now requests it: 3,208 of 5,396 deals carry a value, and
the option label is confirmed as `Subscription - ARR`. The prior result was a
blocked measurement, not a measured zero, and it is now resolved.

Observed billing-model labels: `One-off Project` (2,047), `Subscription - ARR`
(724), `Subscription - Deal` (283), `Retainer Deal` (106), `Deprecated` (24),
`Retainer Top Up` (23), `Subscription - Trial & Pilot Programs` (1), null
(2,188).

## Population and coverage

| Measure | Value |
|---|---|
| Closed-ARR deals | **223** |
| CRM deal amount (**not revenue, not ARR**) | $10,742,820.12 |
| Deal Source populated | 14 (**6.28%**) |
| Deal Source blank | 209 |

Populated values: `X / Twitter` 7, `Paid Search` 4, `Inbound` 2, `Outbound` 1.

## Blank-source split

| Bucket | Deals | CRM deal amount |
|---|---|---|
| Deterministic approved-taxonomy evidence | **0** | $0 |
| Needs human review | **209** | $10,217,597.12 |

Review reasons: 108 `Unknown (no UTM)` with missing quality; 100 with no
associated contact and therefore no channel evidence at all; 1 corrupted UTM.

**No blank closed-ARR deal carries evidence the approved taxonomy can resolve.**
Every clean-evidence channel in this population is already populated. There is
no safe write batch here.

## X / Twitter overlap

All 20 CRM-008-EXEC-CW deals now show `X / Twitter` in the warehouse, so the
manual updates are confirmed landed. By billing model: **7 are
`Subscription - ARR`** and inside the closed-ARR population ($407,667.00
CRM deal amount); 10 are `One-off Project`, 2 `Subscription - Deal`, 1
`Retainer Top Up` — outside it. Those 7 are half of the population's entire
Deal Source coverage.

## Guardrails

- HubSpot `amount` is CRM deal amount, never ARR or recognized revenue.
- Closed-won status alone never establishes ARR.
- No Deal Source is proposed for any record in this task.
