-- stg_hubspot_contacts — staging view over raw.hubspot_contacts.
-- Selects the latest snapshot per contact id (append-only pattern).
-- Uses last-non-null for each field (enrichment snapshots may only carry
-- the enriched field, not the full record).

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
),

latest as (
    select * from ranked where rn = 1
),

-- For each field, get the latest non-null value across all snapshots
latest_non_null as (
    select
        id,
        -- Use last_value with ignore nulls pattern
        (array_agg(email order by extracted_at desc nulls last) filter (where email is not null))[1] as email,
        (array_agg(jobtitle order by extracted_at desc nulls last) filter (where jobtitle is not null))[1] as jobtitle,
        (array_agg(hs_seniority order by extracted_at desc nulls last) filter (where hs_seniority is not null))[1] as hs_seniority,
        (array_agg(createdate order by extracted_at desc nulls last) filter (where createdate is not null))[1] as createdate,
        (array_agg(utm_source order by extracted_at desc nulls last) filter (where utm_source is not null))[1] as utm_source,
        (array_agg(utm_medium order by extracted_at desc nulls last) filter (where utm_medium is not null))[1] as utm_medium,
        (array_agg(utm_campaign order by extracted_at desc nulls last) filter (where utm_campaign is not null))[1] as utm_campaign,
        (array_agg(raw_properties order by extracted_at desc))[1] as raw_properties,
        max(extracted_at) as extracted_at
    from {{ source('raw', 'hubspot_contacts') }}
    group by id
)

select
    lnn.id       as contact_id,
    lnn.extracted_at,
    lnn.email,
    lnn.jobtitle,
    lnn.hs_seniority,
    lnn.createdate,
    lnn.utm_source,
    lnn.utm_medium,
    lnn.utm_campaign,
    lnn.raw_properties
from latest_non_null lnn
