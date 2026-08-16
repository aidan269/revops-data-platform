-- Summary rows must reconcile to the live detail without counting scaffold rows.
with detail as (
    select count(*) as deals, coalesce(sum(closed_won_deal_amount), 0) as amount
    from {{ ref('fct_customer_motion_live') }}
),
reporting as (
    select sum(deal_count) as deals, sum(closed_won_deal_amount) as amount
    from {{ ref('mart_customer_motion_reporting_live') }}
)
select reporting.deals, detail.deals, reporting.amount, detail.amount
from reporting cross join detail
where reporting.deals != detail.deals
   or abs(reporting.amount - detail.amount) > 0.01
