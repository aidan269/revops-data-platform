-- stg_gtm_campaign_deals — distinct campaign→deal association edges.
-- Copied exactly as HubSpot reports them; no deal is inferred into a campaign
-- from UTM, email clicks, web clicks, or contact membership.

select distinct
    campaign_id as gtm_campaign_id,
    deal_id
from {{ source('raw', 'hubspot_gtm_campaign_deals') }}
where campaign_id is not null
  and deal_id is not null
