-- dim_campaign — one row per campaign with type + messaging_theme.
-- Type is deterministic from HubSpot. Messaging theme is advisory (keyword-based here;
-- would be model-assisted via Ollama for ambiguous names). Raw name always preserved.
--
-- Source: analytics_analytics.stg_hubspot_campaigns

with campaigns as (
    select * from {{ ref('stg_hubspot_campaigns') }}
)

select
    campaign_id,
    name as campaign_name,
    type as campaign_type,
    name as raw_campaign_name,
    case
        when lower(name) like '%launch%' then 'product-launch'
        when lower(name) like '%invite%' or lower(name) like '%blackhat%' or lower(name) like '%devcon%'
            or lower(name) like '%breakpoint%' or lower(name) like '%nft%' then 'event-invite'
        when lower(name) like '%webinar%' then 'webinar'
        when lower(name) like '%case study%' then 'case-study'
        when lower(name) like '%security%' or lower(name) like '%research%' or lower(name) like '%risk%'
            or lower(name) like '%mev%' then 'security-research'
        when lower(name) like '%pricing%' or lower(name) like '%discount%' then 'pricing'
        when lower(name) like '%newsletter%' or lower(name) like '%roundup%' or lower(name) like '%tips%'
            or lower(name) like '%onboarding%' or lower(name) like '%re-engagement%' then 'nurture'
        else 'nurture'
    end as messaging_theme
from campaigns
