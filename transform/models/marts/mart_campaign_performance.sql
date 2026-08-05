-- mart_campaign_performance — per campaign and per campaign type.
-- Metrics: touchpoints, contacts influenced, pipeline influenced, closed-won influenced,
-- win rate, won $.
--
-- Source: analytics_analytics.mart_attribution + analytics_analytics.dim_campaign

with attribution as (
    select * from {{ ref('mart_attribution') }}
),
campaigns as (
    select * from {{ ref('dim_campaign') }}
),
campaign_members as (
    select * from {{ ref('stg_campaign_members') }}
),

-- Per campaign
per_campaign as (
    select
        coalesce(a.campaign_id, cm.campaign_id) as campaign_id,
        count(distinct a.touchpoint_id) as touchpoints,
        count(distinct a.contact_id) as contacts_influenced,
        coalesce(sum(a.amount), 0) as pipeline_influenced,
        coalesce(sum(case when a.hs_is_closed_won then a.amount else 0 end), 0) as won_amount,
        count(distinct case when a.hs_is_closed_won then a.deal_id end) as closed_won_influenced
    from campaign_members cm
    left join attribution a on cm.campaign_id = a.campaign_id
    group by coalesce(a.campaign_id, cm.campaign_id)
)

select
    pc.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.messaging_theme,
    pc.touchpoints,
    pc.contacts_influenced,
    pc.pipeline_influenced,
    pc.closed_won_influenced,
    pc.won_amount,
    case
        when pc.contacts_influenced > 0
        then round(pc.closed_won_influenced::numeric / pc.contacts_influenced, 4)
        else 0
    end as win_rate
from per_campaign pc
left join campaigns c on pc.campaign_id = c.campaign_id
order by pc.won_amount desc
