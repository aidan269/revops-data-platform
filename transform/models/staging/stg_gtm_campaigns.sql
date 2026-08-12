-- stg_gtm_campaigns — latest snapshot per GTM Campaign custom-object record.
-- Source: raw.hubspot_gtm_campaigns (HubSpot custom object 2-63647366).
-- This is NOT HubSpot's native Marketing Campaign object.

with ranked as (
    select
        id,
        extracted_at,
        nullif(trim(name), '') as campaign_name,
        created_at,
        updated_at,
        coalesce(archived, false) as archived,
        raw_properties,
        row_number() over (partition by id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_gtm_campaigns') }}
)

select
    id as gtm_campaign_id,
    campaign_name,
    created_at,
    updated_at,
    archived,
    extracted_at,
    raw_properties
from ranked
where rn = 1
