-- stg_contact_company_map — staging view over raw.hubspot_contact_company_map.
-- Latest association per contact_id.

with ranked as (
    select
        contact_id,
        company_id,
        extracted_at,
        row_number() over (partition by contact_id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_contact_company_map') }}
)

select
    contact_id,
    company_id,
    extracted_at
from ranked
where rn = 1
