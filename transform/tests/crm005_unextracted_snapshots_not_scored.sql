select deal_id
from {{ ref('mart_active_pipeline_hygiene_live') }}
where not crm_admin_fields_extracted
  and (
    deal_owner_gap_status <> 'unavailable_in_current_snapshot_not_scored'
    or next_step_gap_or_staleness_status <> 'unavailable_in_current_snapshot_not_scored'
    or product_service_gap_status <> 'unavailable_in_current_snapshot_not_scored'
    or billing_model_gap_status <> 'unavailable_in_current_snapshot_not_scored'
  )
