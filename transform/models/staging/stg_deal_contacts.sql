-- stg_deal_contacts — staging view over raw.hubspot_deal_contacts.
-- Latest association per deal_id.

with ranked as (
    select
        deal_id,
        contact_id,
        extracted_at,
        row_number() over (partition by deal_id, contact_id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_deal_contacts') }}
)

select
    deal_id,
    contact_id,
    extracted_at
from ranked
where rn = 1
