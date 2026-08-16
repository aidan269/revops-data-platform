-- First-touch credit must reconcile to one deal amount per eligible
-- contact/deal pair. mart_channel_performance has a different grain and can
-- include deals without a pre-creation touch, so it is not a valid comparator.
{{ config(store_failures = true) }}

with attribution as (
    select
        contact_id,
        deal_id,
        max(amount) as deal_amount,
        sum(first_touch_credit) as first_touch_amount
    from {{ ref('mart_attribution') }}
    group by 1, 2
)
select
    contact_id,
    deal_id,
    deal_amount,
    first_touch_amount
from attribution
where abs(coalesce(first_touch_amount, 0) - coalesce(deal_amount, 0)) > 0.01
