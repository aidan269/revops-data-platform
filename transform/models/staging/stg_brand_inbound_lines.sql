-- stg_brand_inbound_lines — staging view over raw.brand_inbound_lines.
--
-- Historical human-maintained evidence, NOT current CRM truth. Original values
-- are passed through verbatim; parsed companions sit alongside them. Duplicate
-- source rows remain individually observable via source_row_number.

select
    line_id,
    source_sha256,
    source_filename,
    source_row_number,
    report_month_filled                 as report_month,
    nullif(trim(deal_name_raw), '')     as deal_name,
    nullif(trim(organisation_name_raw), '') as organisation_name,
    nullif(trim(source_raw), '')        as historical_source,
    nullif(trim(current_stage_raw), '') as historical_stage,
    nullif(trim(ae_name_raw), '')       as ae_name,
    hubspot_object_type,
    hubspot_record_id,
    is_deal_link,
    case when is_deal_link then hubspot_record_id end as deal_id,
    case when hubspot_object_type = '0-2' then hubspot_record_id end as company_id,
    days_to_discovery_num,
    days_to_scope_complete_num,
    days_to_call_booked_num,
    days_to_next_follow_up_num,
    deals_num,
    gmv_num,
    revenue_num,
    arr_num,
    -- verbatim originals retained for replay
    month_raw,
    deal_name_raw,
    source_raw,
    hubspot_link_raw,
    raw_row,
    imported_at,
    authorizes_crm_change
from {{ source('raw', 'brand_inbound_lines') }}
