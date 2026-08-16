-- Investor detail must contain every and only live closed-won deal.
with expected as (
    select count(*) as deals, coalesce(sum(amount), 0) as amount
    from {{ ref('mart_gtm_lifecycle_live') }}
    where hs_is_closed_won = true
),
actual as (
    select count(*) as deals, coalesce(sum(closed_won_deal_amount), 0) as amount
    from {{ ref('fct_customer_motion_live') }}
)
select actual.deals, expected.deals, actual.amount, expected.amount
from actual cross join expected
where actual.deals != expected.deals
   or abs(actual.amount - expected.amount) > 0.01
