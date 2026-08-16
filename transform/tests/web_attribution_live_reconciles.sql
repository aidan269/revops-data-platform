-- Detail must contain every and only live deal, with amounts unchanged.
with expected as (
    select count(*) as deals, coalesce(sum(amount), 0) as amount
    from {{ ref('mart_gtm_lifecycle_live') }}
),
actual as (
    select count(*) as deals, coalesce(sum(deal_amount), 0) as amount
    from {{ ref('fct_web_attribution_readiness_live') }}
)
select actual.deals, expected.deals, actual.amount, expected.amount
from actual cross join expected
where actual.deals != expected.deals
   or abs(actual.amount - expected.amount) > 0.01
