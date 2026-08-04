-- mart_channel_performance — one row per channel with funnel metrics.
-- Answers: which channel converts the most?
--
-- Metrics per channel:
--   contacts          — total contacts in this channel
--   deals_created     — total deals associated to contacts in this channel
--   closed_won        — deals where hs_is_closed_won = true (carried as-is from HubSpot)
--   win_rate_contacts — won / contacts (primary win rate)
--   win_rate_deals    — won / deals (secondary win rate)
--   pipeline_amount   — sum of deal amount for all deals
--   won_amount        — sum of deal amount for won deals
--   avg_days_to_close — avg(closedate - createdate) for won deals
--
-- The "Unknown (corrupted UTM)" channel is kept as its own row — never hidden.
--
-- Sources:
--   analytics_analytics.int_contact_channel (channel assignment)
--   analytics_analytics.bridge_deal_contact (deal↔contact links)
--   analytics_analytics.dim_deal (deal facts)

with contact_channels as (
    select * from {{ ref('int_contact_channel') }}
),
deal_contacts as (
    select * from {{ ref('bridge_deal_contact') }}
),
deals as (
    select * from {{ ref('dim_deal') }}
),

-- Join deals to contacts to get channel attribution
deal_channel as (
    select
        d.deal_id,
        d.amount,
        d.hs_is_closed_won,
        d.createdate,
        d.closedate,
        cc.channel,
        cc.contact_id
    from deals d
    inner join deal_contacts dc on d.deal_id = dc.deal_id
    inner join contact_channels cc on dc.contact_id = cc.contact_id
)

select
    cc.channel,
    -- Contacts: distinct count (some contacts may have no deal)
    count(distinct cc.contact_id) as contacts,

    -- Deals
    count(distinct dc.deal_id) as deals_created,
    count(distinct case when dc.hs_is_closed_won then dc.deal_id end) as closed_won,

    -- Win rates
    case
        when count(distinct cc.contact_id) > 0
        then round(
            count(distinct case when dc.hs_is_closed_won then dc.deal_id end)::numeric
            / count(distinct cc.contact_id), 4)
        else 0
    end as win_rate_contacts,

    case
        when count(distinct dc.deal_id) > 0
        then round(
            count(distinct case when dc.hs_is_closed_won then dc.deal_id end)::numeric
            / count(distinct dc.deal_id), 4)
        else 0
    end as win_rate_deals,

    -- Pipeline $ (all deals)
    coalesce(sum(dc.amount), 0) as pipeline_amount,

    -- Won $ (won deals only)
    coalesce(sum(case when dc.hs_is_closed_won then dc.amount else 0 end), 0) as won_amount,

    -- Avg days to close (won deals only)
    case
        when count(case when dc.hs_is_closed_won then 1 end) > 0
        then round(avg(
            case when dc.hs_is_closed_won
                 then extract(epoch from (dc.closedate - dc.createdate)) / 86400
            end
        ), 1)
        else null
    end as avg_days_to_close

from contact_channels cc
left join deal_channel dc on cc.contact_id = dc.contact_id
group by cc.channel
order by won_amount desc
