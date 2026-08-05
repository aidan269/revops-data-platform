-- fct_touchpoint — one row per contact-touchpoint.
-- The spine for attribution. Combines engagements + the original contact UTM as touch 0.
--
-- Touch types:
--   1. acquisition — the contact's original UTM (first-touch, always timestamp = createdate)
--   2. email_open, email_click, form_submission, meeting — from engagements
--
-- Channel is assigned per funnel_definitions.md (deterministic UTM → channel).
-- Campaign_id is linked where available.
--
-- Sources:
--   analytics_analytics.stg_hubspot_contacts (UTM + createdate)
--   analytics_analytics.stg_hubspot_engagements (engagement events)
--   analytics_analytics.int_contact_channel (channel assignment)

with contacts as (
    select contact_id, utm_source, utm_medium, utm_campaign, createdate
    from {{ ref('stg_hubspot_contacts') }}
),
channels as (
    select contact_id, channel
    from {{ ref('int_contact_channel') }}
),
engagements as (
    select
        engagement_id,
        contact_id,
        engagement_type,
        "timestamp",
        campaign_id,
        asset_id
    from {{ ref('stg_hubspot_engagements') }}
)

-- Touch 0: acquisition (original UTM)
select
    c.contact_id || '_acq' as touchpoint_id,
    c.contact_id,
    coalesce(c.createdate, '2024-11-01T00:00:00Z'::timestamptz) as touchpoint_timestamp,
    'acquisition' as engagement_type,
    ch.channel,
    c.utm_source,
    c.utm_medium,
    c.utm_campaign,
    null::text as campaign_id,
    null::text as asset_id
from contacts c
inner join channels ch on c.contact_id = ch.contact_id

union all

-- Engagement touchpoints
select
    e.contact_id || '_eng_' || e.engagement_id as touchpoint_id,
    e.contact_id,
    e."timestamp" as touchpoint_timestamp,
    e.engagement_type,
    -- For engagements, channel comes from the contact's first-touch channel
    ch.channel,
    c.utm_source,
    c.utm_medium,
    c.utm_campaign,
    e.campaign_id,
    e.asset_id
from engagements e
inner join channels ch on e.contact_id = ch.contact_id
inner join contacts c on e.contact_id = c.contact_id
