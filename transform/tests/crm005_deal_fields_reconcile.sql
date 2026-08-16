with latest as (
    select distinct on (id)
        id as deal_id,
        nullif(raw_properties ->> '_crm_admin_deal_owner_id', '') as deal_owner_id,
        nullif(raw_properties ->> '_crm_admin_next_step', '') as next_step,
        nullif(raw_properties ->> '_crm_admin_product_service', '') as product_service,
        nullif(raw_properties ->> '_crm_admin_billing_model', '') as billing_model,
        coalesce((raw_properties ->> '_crm_admin_fields_extracted')::boolean, false)
          as crm_admin_fields_extracted
    from {{ source('raw', 'hubspot_deals') }}
    order by id, extracted_at desc
)
select l.deal_id
from latest l join {{ ref('stg_hubspot_deals') }} s using (deal_id)
where l.deal_owner_id is distinct from s.deal_owner_id
   or l.next_step is distinct from s.next_step
   or l.product_service is distinct from s.product_service
   or l.billing_model is distinct from s.billing_model
   or l.crm_admin_fields_extracted is distinct from s.crm_admin_fields_extracted
