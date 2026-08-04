-- stg_hubspot_companies — staging view over raw.hubspot_companies.
-- Selects the latest snapshot per company id (append-only pattern).

with ranked as (
    select
        id,
        extracted_at,
        name,
        domain,
        industry,
        numberofemployees,
        hs_employee_range,
        raw_properties,
        row_number() over (partition by id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_companies') }}
)

select
    id                as company_id,
    extracted_at,
    name              as company_name,
    domain,
    industry,
    numberofemployees,
    hs_employee_range,
    raw_properties
from ranked
where rn = 1
