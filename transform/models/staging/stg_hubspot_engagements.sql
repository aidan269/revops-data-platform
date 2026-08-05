-- stg_hubspot_engagements — staging view over raw.hubspot_engagements.
-- Latest snapshot per engagement id.

with ranked as (
    select *,
        row_number() over (partition by id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_engagements') }}
)
select
    id as engagement_id,
    extracted_at,
    contact_id,
    type as engagement_type,
    "timestamp",
    campaign_id,
    asset_id,
    raw_properties
from ranked where rn = 1
