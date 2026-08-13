-- Latest direct Deal → Company associations from HubSpot.

with ranked as (
    select
        deal_id,
        company_id,
        extracted_at,
        row_number() over (
            partition by deal_id, company_id
            order by extracted_at desc
        ) as rn
    from {{ source('raw', 'hubspot_deal_companies') }}
)

select deal_id, company_id, extracted_at
from ranked
where rn = 1
