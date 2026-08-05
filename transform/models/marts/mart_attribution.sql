-- mart_attribution — per touchpoint, credit under 3 attribution models.
-- Roll up to channel / campaign / campaign-type.
-- First-touch MUST reconcile to mart_channel_performance (regression guard).
--
-- Attribution models (per funnel_definitions.md):
--   first_touch: 100% credit to the acquisition touch (earliest touchpoint per contact)
--   last_touch: 100% credit to the touch before the deal was created
--   linear: credit split evenly across all touches
--
-- Credit is in deal dollars: each touchpoint gets a share of the deal's amount
-- (if the deal is won, the credit goes to won_amount; if open, pipeline_amount).
--
-- Sources:
--   analytics_analytics.fct_touchpoint (the spine)
--   analytics_analytics.bridge_deal_contact (deal↔contact links)
--   analytics_analytics.dim_deal (deal facts)

with touchpoints as (
    select * from {{ ref('fct_touchpoint') }}
),
deal_contacts as (
    select * from {{ ref('bridge_deal_contact') }}
),
deals as (
    select * from {{ ref('dim_deal') }}
),

-- Join touchpoints to deals (via contact)
touchpoint_deals as (
    select
        tp.touchpoint_id,
        tp.contact_id,
        tp.touchpoint_timestamp,
        tp.engagement_type,
        tp.channel,
        tp.campaign_id,
        tp.asset_id,
        d.deal_id,
        d.amount,
        d.hs_is_closed_won,
        d.createdate as deal_createdate,
        d.closedate as deal_closedate
    from touchpoints tp
    inner join deal_contacts dc on tp.contact_id = dc.contact_id
    inner join deals d on dc.deal_id = d.deal_id
),

-- Rank touchpoints per (contact, deal) for first/last touch
ranked as (
    select
        *,
        row_number() over (
            partition by contact_id, deal_id
            order by touchpoint_timestamp asc
        ) as touch_rank_asc,
        row_number() over (
            partition by contact_id, deal_id
            order by touchpoint_timestamp desc
        ) as touch_rank_desc,
        count(*) over (
            partition by contact_id, deal_id
        ) as total_touches
    from touchpoint_deals
    where touchpoint_timestamp <= deal_createdate  -- only touches before deal creation
)

select
    touchpoint_id,
    contact_id,
    deal_id,
    channel,
    campaign_id,
    engagement_type,
    touchpoint_timestamp,
    amount,
    hs_is_closed_won,
    -- First-touch: 100% credit to touch_rank_asc = 1
    case when touch_rank_asc = 1 then amount else 0 end as first_touch_credit,
    -- Last-touch: 100% credit to touch_rank_desc = 1 (last touch before deal)
    case when touch_rank_desc = 1 then amount else 0 end as last_touch_credit,
    -- Linear: credit split evenly across all touches
    round(amount::numeric / total_touches, 2) as linear_credit
from ranked
