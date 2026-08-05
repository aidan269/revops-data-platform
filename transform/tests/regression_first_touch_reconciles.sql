-- Regression guard: first-touch attribution reconciles to mart_channel_performance.
-- The sum of first_touch_credit where hs_is_closed_won = true, grouped by channel,
-- must match the won_amount in mart_channel_performance for each channel.
-- If this fails, the attribution model diverged from the channel mart.
{{ config(store_failures = true) }}

with attribution as (
    select channel, sum(first_touch_credit) as ft_won_amount
    from {{ ref('mart_attribution') }}
    where hs_is_closed_won = true
    group by channel
),
channel_mart as (
    select channel, won_amount
    from {{ ref('mart_channel_performance') }}
)
select
    coalesce(a.channel, c.channel) as channel,
    a.ft_won_amount as attribution_won,
    c.won_amount as channel_mart_won,
    abs(a.ft_won_amount - c.won_amount) as delta
from attribution a
full outer join channel_mart c on a.channel = c.channel
where abs(coalesce(a.ft_won_amount, 0) - coalesce(c.won_amount, 0)) > 1  -- $1 tolerance
