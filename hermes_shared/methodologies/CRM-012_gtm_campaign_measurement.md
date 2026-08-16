# CRM-012 — GTM Campaign measurement layer

Read-only. No HubSpot write, no workflow, no contact or deal creation, no
association change. The layer reads the CRM; it never edits it.

## What this measures

Marketing is accountable for qualified pipeline, SQLs and demos — not clicks or
form fills. This layer compares GTM campaigns (events, LinkedIn lead-gen,
list-based outbound) by the contacts, deals, pipeline and closed-won outcomes
they are **directly associated with** in HubSpot.

Ground truth is the custom object **GTM Campaigns (`2-63647366`)**, not HubSpot's
native Marketing Campaign object. `raw.hubspot_campaigns` remains a separate
table and the two are never mixed.

## Sourced vs influenced — the distinction that governs this layer

| | Meaning | Supported here? |
|---|---|---|
| **Sourced** | The campaign created the opportunity; it is the reason the deal exists | **No** |
| **Influenced** | The campaign is directly associated with the deal in HubSpot | **Yes** |

Every metric is **influenced-by-association**. The measurement layer knows that
a reviewer attached a deal to a campaign. It does not know *why*, and it has no
first-touch evidence tying campaign involvement to deal creation. Column names
say so (`influenced_crm_deal_amount`), and every tool response carries an
`attribution_basis` field.

Consequence: two campaigns associated with the same deal each count it. These
figures do not sum to a company total and must never be added across campaigns.

## CRM deal amount vs ARR and revenue

Amounts are the HubSpot `amount` property. They are **not ARR and not recognized
revenue**. Every amount column is suffixed `_crm_deal_amount`, and the mart
carries `amount_basis = 'crm_deal_amount_not_arr_not_recognized_revenue'`.

Closed ARR is a separate, stricter definition (Viv's): Closed Won **and**
`billing_model = 'Subscription - ARR'`. The mart carries `closed_arr_deals` as a
cross-reference count only — no ARR amount is exposed, because ARR amounts
require Finance-reviewed lineage this warehouse does not hold.

## Directly observed evidence vs unsupported claims

**Observed, and safe to state:**

- The campaign has N associated contacts and M associated deals.
- Those deals carry X of CRM deal amount, of which Y are closed won.
- Open pipeline is the associated deals that are neither won nor lost.

**Not supported, and must not be stated:**

- That a campaign *sourced*, *generated*, or *drove* a deal.
- Any ROI or return figure. **No campaign cost or spend exists anywhere in this
  warehouse**, so ROI is not merely unproven — it is uncomputable.
- Any revenue or ARR claim derived from CRM deal amount.
- Campaign-level meeting, form or email-engagement counts. Those engagements
  attach to contacts, not to the GTM Campaign object. Counting them per campaign
  would require inferring campaign involvement from contact activity, which this
  layer forbids.

## Explicitly forbidden inference paths

No deal or contact enters a campaign because of UTM parameters, email clicks,
web clicks, or contact membership. Association edges are copied exactly as
HubSpot reports them. If a reviewer has not attached a record, it is absent —
and a missing association is indistinguishable from genuine non-influence.

## Association-quality gaps

The mart flags, per campaign: no associated contacts, no associated deals,
missing campaign name, an associated deal absent from the live warehouse, and an
associated deal with no amount. A campaign is `measurable_influence` only when it
has at least one resolvable deal; otherwise `not_yet_measurable`.

These gaps are reported alongside every metric. A campaign with strong numbers
and heavy gaps is a data-quality finding, not a performance finding.

## CRM facts reconciled (not written)

Recorded as of the CRM-012 build for reconciliation testing only:

- **Q326 - Apex Free Exploitability Review** — pre-existing; Rahma Hafi and the
  existing Apex - Groupe APICIL deal attached.
- **Demo vs PLG** — Snehal Kumar and Gillian Dom attached, with the existing
  Aptean and Sierra Nevada deals.
- **CloudSec List** — Lily Chau (`lily@amplitude.com`) and her existing
  "- Amplitude" deal. Gillian Dom and Sierra Nevada were deliberately removed and
  must remain associated only with Demo vs PLG.

The reconciliation tests assert these hold once extraction has run. They never
create or repair an association; a failure is a review finding for a human.
