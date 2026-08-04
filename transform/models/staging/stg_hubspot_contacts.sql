-- stg_hubspot_contacts — staging view over raw.hubspot_contacts.
-- Selects the latest snapshot per contact id (append-only pattern).
-- No business logic — just type casting and dedup to latest.

with ranked as (
    select
        id,
        extracted_at,
        email,
        jobtitle,
        hs_seniority,
        createdate,
        utm_source,
        utm_medium,
        utm_campaign,
        raw_properties,
        row_number() over (partition by id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_contacts') }}
)

select
    id            as contact_id,
    extracted_at,
    email,
    jobtitle,
    hs_seniority,
    createdate,
    utm_source,
    utm_medium,
    utm_campaign,
    raw_properties
from ranked
where rn = 1
