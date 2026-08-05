-- stg_campaign_members — staging view over raw.hubspot_campaign_members.
-- Latest association per (campaign_id, contact_id).

with ranked as (
    select *,
        row_number() over (partition by campaign_id, contact_id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_campaign_members') }}
)
select campaign_id, contact_id, extracted_at
from ranked where rn = 1
