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
        deal_source,
        -- CRM-010: native HubSpot Original Traffic Source (hs_analytics_source).
        nullif(original_traffic_source, '') as original_traffic_source,
        nullif(raw_properties ->> '_crm_admin_deal_owner_id', '') as deal_owner_id,
        nullif(raw_properties ->> '_crm_admin_next_step', '') as next_step,
        case
            when raw_properties ->> '_crm_admin_next_step_updated_at' ~ '^[0-9]{13}$'
                then to_timestamp((raw_properties ->> '_crm_admin_next_step_updated_at')::bigint / 1000.0)
            when raw_properties ->> '_crm_admin_next_step_updated_at' ~ '^\\d{4}-\\d{2}-\\d{2}'
                then (raw_properties ->> '_crm_admin_next_step_updated_at')::timestamptz
        end as next_step_updated_at,
        nullif(raw_properties ->> '_crm_admin_product_service', '') as product_service,
        nullif(raw_properties ->> '_crm_admin_billing_model', '') as billing_model,
        coalesce((raw_properties ->> '_crm_admin_fields_extracted')::boolean, false)
            as crm_admin_fields_extracted,
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
    deal_source,
    original_traffic_source,
    deal_owner_id,
    next_step,
    next_step_updated_at,
    product_service,
    billing_model,
    crm_admin_fields_extracted,
    raw_properties
from ranked
where rn = 1
