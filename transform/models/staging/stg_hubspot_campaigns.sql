-- stg_hubspot_campaigns — staging view over raw.hubspot_campaigns.
-- Latest snapshot per campaign id.

with ranked as (
    select *,
        row_number() over (partition by id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_campaigns') }}
)
select id as campaign_id, extracted_at, name, type, raw_properties
from ranked where rn = 1
