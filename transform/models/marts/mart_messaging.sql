-- mart_messaging — per messaging_theme, two lenses:
--   (a) engagement rate (email_open / email_click counts + rates)
--   (b) downstream conversion (influenced pipeline & closed-won)
--
-- Source: analytics_analytics.fct_touchpoint + dim_campaign + mart_attribution

with touchpoints as (
    select * from {{ ref('fct_touchpoint') }}
),
campaigns as (
    select * from {{ ref('dim_campaign') }}
),
attribution as (
    select * from {{ ref('mart_attribution') }}
),

-- Link touchpoints to campaigns to get messaging_theme
tp_with_theme as (
    select
        tp.touchpoint_id,
        tp.contact_id,
        tp.engagement_type,
        tp.campaign_id,
        coalesce(c.messaging_theme, 'no-campaign') as messaging_theme
    from touchpoints tp
    left join campaigns c on tp.campaign_id = c.campaign_id
    where tp.campaign_id is not null
),

-- Engagement metrics per theme
engagement as (
    select
        messaging_theme,
        count(*) as total_touchpoints,
        count(case when engagement_type = 'email_open' then 1 end) as email_opens,
        count(case when engagement_type = 'email_click' then 1 end) as email_clicks,
        count(case when engagement_type = 'form_submission' then 1 end) as form_submissions,
        count(case when engagement_type = 'meeting' then 1 end) as meetings,
        count(distinct contact_id) as contacts_engaged
    from tp_with_theme
    group by messaging_theme
),

-- Conversion metrics per theme (via attribution)
conversion as (
    select
        coalesce(c.messaging_theme, 'no-campaign') as messaging_theme,
        count(distinct a.contact_id) as contacts_influenced,
        coalesce(sum(a.linear_credit), 0) as pipeline_influenced,
        coalesce(sum(case when a.hs_is_closed_won then a.linear_credit else 0 end), 0) as won_amount,
        count(distinct case when a.hs_is_closed_won then a.deal_id end) as closed_won_deals
    from attribution a
    left join campaigns c on a.campaign_id = c.campaign_id
    where a.campaign_id is not null
    group by coalesce(c.messaging_theme, 'no-campaign')
)

select
    e.messaging_theme,
    -- Lens A: engagement
    e.total_touchpoints,
    e.email_opens,
    e.email_clicks,
    e.form_submissions,
    e.meetings,
    e.contacts_engaged,
    case
        when e.total_touchpoints > 0
        then round((e.email_clicks::numeric / e.email_opens) * 100, 2)
        else 0
    end as click_to_open_rate,
    -- Lens B: conversion
    coalesce(c.contacts_influenced, 0) as contacts_influenced,
    coalesce(c.pipeline_influenced, 0) as pipeline_influenced,
    coalesce(c.won_amount, 0) as won_amount,
    coalesce(c.closed_won_deals, 0) as closed_won_deals,
    case
        when c.contacts_influenced > 0
        then round(c.closed_won_deals::numeric / c.contacts_influenced, 4)
        else 0
    end as conversion_rate
from engagement e
left join conversion c on e.messaging_theme = c.messaging_theme
order by c.won_amount desc nulls last
