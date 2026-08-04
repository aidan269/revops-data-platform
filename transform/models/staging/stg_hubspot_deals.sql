-- stg_hubspot_deals — staging view over raw.hubspot_deals.
-- Latest snapshot per deal id (append-only pattern).

with ranked as (
    select
        id,
        extracted_at,
        amount,
        dealstage,
        pipeline,
        hs_is_closed_won,
        createdate,
        closedate,
        raw_properties,
        row_number() over (partition by id order by extracted_at desc) as rn
    from {{ source('raw', 'hubspot_deals') }}
)

select
    id              as deal_id,
    extracted_at,
    amount,
    dealstage,
    pipeline,
    hs_is_closed_won,
    createdate,
    closedate,
    raw_properties
from ranked
where rn = 1
