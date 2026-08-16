# GTM lifecycle data contract

`mart_gtm_lifecycle` is the canonical answer to: is this revenue a net-new
customer, an audit-to-ARR conversion, or an expansion?

## What the warehouse can prove today

- `first_known_company_win`: the first closed-won deal for an associated
  company in retained warehouse history.
- `repeat_company_win`: a later closed-won deal for that company.
- First-touch channel and raw UTM value on the selected associated contact.

These are not substitutes for commercial motion. A first-known company win
is not automatically net-new ARR, and a repeat-company win is not
automatically an expansion.

## Reviewed motion override

Until the CRM provides an immutable service/product lineage field, maintain
`transform/seeds/gtm_deal_motion_overrides.csv`. Allowed `customer_motion`
values are:

- `net_new_arr`
- `audit_to_arr_conversion`
- `expansion`
- `renewal`
- `other_non_arr`

Every override needs an evidence note, reviewer, and review date. The dbt
model marks unreviewed rows as `unclassified`; it never silently infers a
commercial motion.

## CRM instrumentation requirement

At form submission, capture and preserve on the contact: original UTM source,
medium, campaign, landing page, referrer, first conversion timestamp, and
form identifier. When a deal is created, copy immutable original-source
fields to the deal and record the service/product motion. Do not overwrite
the original values on later touches. Associate the deal to the company and
primary buying contact with timestamps.

The four required funnel events are form submission, qualified contact,
deal creation, and closed-won/lost. Every event must carry a stable contact
or deal ID so the full journey can be measured without inferred joins.
