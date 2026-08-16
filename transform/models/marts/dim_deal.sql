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
    deal_source,
    original_traffic_source,
    deal_owner_id,
    next_step,
    next_step_updated_at,
    product_service,
    billing_model,
    crm_admin_fields_extracted,
    extracted_at
from {{ ref('stg_hubspot_deals') }}
