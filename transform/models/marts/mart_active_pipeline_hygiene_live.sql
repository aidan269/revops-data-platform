-- CRM-004/005: live-only, observable active-pipeline hygiene queue.
-- Historical snapshots without CRM-005 extraction provenance are not treated
-- as missing values for owner/next-step/product/billing fields.

with open_deals as (
    select
        d.*,
        s.pipeline_label,
        s.stage_label,
        coalesce(dc.direct_company_count, 0) as direct_company_count,
        dc.direct_company_ids,
        w.utm_evidence_status,
        w.web_form_evidence_status,
        case
            when d.first_touch_channel = 'Google Ads' then 'Paid Search'
            when d.first_touch_channel in ('Direct', 'Webflow / Cantina') then 'Website / Direct'
            when d.first_touch_channel = 'Email / In-app' then 'Email / Nurture'
            when d.first_touch_channel = 'Organic Search' then 'Organic Search'
        end as approved_source_candidate
    from {{ ref('mart_gtm_lifecycle_live') }} d
    left join {{ ref('stg_hubspot_deal_stages') }} s
      on s.pipeline_id = d.pipeline and s.stage_id = d.dealstage
    left join (
        select deal_id, count(*) as direct_company_count,
               string_agg(company_id, ',' order by company_id) as direct_company_ids
        from {{ ref('stg_deal_companies') }} group by 1
    ) dc using (deal_id)
    left join {{ ref('fct_web_attribution_readiness_live') }} w using (deal_id)
    where coalesce(s.is_closed, false) = false
),
classified as (
    select *,
        amount >= 60000 as high_crm_deal_amount,
        deal_closedate between current_date and current_date + 30 as close_within_30_days,
        case
            when deal_closedate is null then 'missing'
            when deal_closedate < deal_createdate::date then 'implausible_before_deal_created'
            when deal_closedate > current_date + 730 then 'implausible_more_than_730_days_future'
            when deal_closedate < current_date then 'past'
            when deal_closedate <= current_date + 30 then 'within_30_days'
            else 'future_more_than_30_days'
        end as close_date_status,
        coalesce(trim(hubspot_deal_source), '') = '' as gap_blank_deal_source,
        direct_company_count = 0 as gap_missing_direct_company,
        (deal_closedate is null or deal_closedate < current_date
          or deal_closedate < deal_createdate::date or deal_closedate > current_date + 730)
          as gap_close_date
    from open_deals
),
scored as (
    select *,
        case
            when not crm_admin_fields_extracted then 'unavailable_in_current_snapshot_not_scored'
            when deal_owner_id is null then 'missing'
            else 'populated'
        end as deal_owner_gap_status,
        case
            when not crm_admin_fields_extracted then 'unavailable_in_current_snapshot_not_scored'
            when next_step is null then 'missing'
            when next_step_updated_at is null then 'timestamp_unavailable_not_scored'
            when next_step_updated_at < current_timestamp - interval '30 days' then 'stale_over_30_days'
            else 'current'
        end as next_step_gap_or_staleness_status,
        case when not crm_admin_fields_extracted then 'unavailable_in_current_snapshot_not_scored'
             when product_service is null then 'missing' else 'populated' end as product_service_gap_status,
        case when not crm_admin_fields_extracted then 'unavailable_in_current_snapshot_not_scored'
             when billing_model is null then 'missing' else 'populated' end as billing_model_gap_status
    from classified
),
candidates as (
    select *,
        case
            when high_crm_deal_amount and (close_within_30_days or gap_close_date) then 'P0_high_value_close_risk'
            when close_within_30_days or gap_close_date then 'P1_close_date_urgent'
            when high_crm_deal_amount then 'P2_high_value'
            else 'P3_standard'
        end as priority
    from scored
    where gap_blank_deal_source or gap_missing_direct_company or gap_close_date
       or deal_owner_gap_status = 'missing'
       or next_step_gap_or_staleness_status in ('missing', 'stale_over_30_days')
       or product_service_gap_status = 'missing'
       or billing_model_gap_status = 'missing'
)
select
    priority, deal_id, coalesce(pipeline_label, pipeline, 'Unmapped pipeline') as pipeline_name,
    coalesce(stage_label, dealstage, 'Unmapped stage') as stage_name,
    amount as crm_deal_amount, deal_createdate, deal_closedate,
    case when deal_closedate is not null then deal_closedate - current_date end as days_until_close,
    high_crm_deal_amount, close_within_30_days, close_date_status,
    deal_owner_id, deal_owner_gap_status, next_step, next_step_updated_at,
    next_step_gap_or_staleness_status, product_service, product_service_gap_status,
    billing_model, billing_model_gap_status, crm_admin_fields_extracted,
    hubspot_deal_source as current_deal_source, first_touch_channel, first_touch_utm_source,
    utm_evidence_status, web_form_evidence_status,
    case when not gap_blank_deal_source then 'populated_no_gap'
         when approved_source_candidate is not null and utm_evidence_status = 'clean_utm'
           then 'human_review_existing_approved_mapping'
         else 'remain_blank_no_approved_deterministic_evidence' end as deal_source_gap_status,
    case when gap_blank_deal_source and approved_source_candidate is not null
              and utm_evidence_status = 'clean_utm' then approved_source_candidate end
      as review_only_deal_source_candidate,
    direct_company_count, direct_company_ids,
    concat_ws('; ',
      case when gap_close_date then 'close_date_' || close_date_status end,
      case when deal_owner_gap_status = 'missing' then 'missing_deal_owner' end,
      case when next_step_gap_or_staleness_status = 'missing' then 'missing_next_step' end,
      case when next_step_gap_or_staleness_status = 'stale_over_30_days' then 'stale_next_step' end,
      case when product_service_gap_status = 'missing' then 'missing_product_service' end,
      case when billing_model_gap_status = 'missing' then 'missing_billing_model' end,
      case when gap_blank_deal_source then 'blank_deal_source' end,
      case when gap_missing_direct_company then 'missing_direct_company_association' end
    ) as observable_gaps,
    'Sales Ops routes to the current deal owner; Marketing Ops reviews Deal Source; Sales Ops reviews company associations.' as recommended_human_owner,
    'Review only the listed observable gaps. Do not infer or automatically populate any value.' as recommended_human_action,
    false as execution_authorized
from candidates
