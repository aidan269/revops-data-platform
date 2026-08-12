-- stg_gtm_campaign_contacts — distinct campaign→contact association edges.
-- Association edges are copied exactly as HubSpot reports them. Membership is
-- evidence of association only, never of attribution.

select distinct
    campaign_id as gtm_campaign_id,
    contact_id
from {{ source('raw', 'hubspot_gtm_campaign_contacts') }}
where campaign_id is not null
  and contact_id is not null
