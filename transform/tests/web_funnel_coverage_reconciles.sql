-- The first checkpoint must reconcile exactly to the live detail population.
with expected as (
    select count(*) as deals,
           count(*) filter (where hs_is_closed_won) as wins,
           coalesce(sum(deal_amount), 0) as amount
    from {{ ref('fct_web_attribution_readiness_live') }}
),
actual as (
    select deal_count as deals, closed_won_deal_count as wins, deal_amount as amount
    from {{ ref('mart_web_funnel_coverage_live') }}
    where funnel_stage = 'live_deal_population'
)
select actual.deals, expected.deals, actual.wins, expected.wins, actual.amount, expected.amount
from actual cross join expected
where actual.deals != expected.deals
   or actual.wins != expected.wins
   or abs(actual.amount - expected.amount) > 0.01
