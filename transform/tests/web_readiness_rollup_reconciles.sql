-- Readiness groups must partition the live deal detail exactly once.
with expected as (
    select count(*) as deals,
           count(*) filter (where hs_is_closed_won) as wins
    from {{ ref('fct_web_attribution_readiness_live') }}
),
actual as (
    select sum(live_deals) as deals, sum(live_closed_won_deals) as wins
    from {{ ref('mart_web_attribution_readiness_live') }}
)
select actual.deals, expected.deals, actual.wins, expected.wins
from actual cross join expected
where actual.deals != expected.deals or actual.wins != expected.wins
