-- dim_deal — one row per deal (latest snapshot).
-- Source: analytics_analytics.stg_hubspot_deals

select
    deal_id,
    amount,
    dealstage,
    pipeline,
    hs_is_closed_won,
    createdate,
    closedate,
    extracted_at
from {{ ref('stg_hubspot_deals') }}
