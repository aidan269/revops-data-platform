-- A review queue, not an automation: current deals whose direct company
-- association or Deal Source needs human or evidence-backed remediation.

with deals as (
    select * from {{ ref('mart_gtm_lifecycle_live') }}
),
direct_companies as (
    select
        deal_id,
        count(*) as direct_company_count,
        string_agg(company_id, ', ' order by company_id) as direct_company_ids
    from {{ ref('stg_deal_companies') }}
    group by 1
),
stages as (
    select * from {{ ref('stg_hubspot_deal_stages') }}
)

select
    d.deal_id,
    coalesce(s.pipeline_label, d.pipeline, 'Unmapped pipeline') as pipeline_name,
    coalesce(s.stage_label, d.dealstage, 'Unmapped stage') as stage_name,
    d.amount,
    d.hs_is_closed_won,
    d.deal_createdate,
    d.deal_closedate,
    d.hubspot_deal_source,
    d.first_touch_channel,
    case
        when d.first_touch_channel = 'Google Ads' then 'Paid Search'
        when d.first_touch_channel in ('Direct', 'Webflow / Cantina') then 'Website / Direct'
        when d.first_touch_channel = 'Email / In-app' then 'Email / Nurture'
        when d.first_touch_channel = 'Organic Search' then 'Organic Search'
    end as suggested_deal_source,
    case
        when coalesce(trim(d.hubspot_deal_source), '') <> '' then 'already_populated'
        when d.first_touch_channel in (
            'Google Ads', 'Direct', 'Webflow / Cantina', 'Email / In-app', 'Organic Search'
        ) then 'high_confidence_first_touch'
        else 'manual_review_required'
    end as deal_source_review_status,
    coalesce(dc.direct_company_count, 0) as direct_company_count,
    dc.direct_company_ids,
    case
        when coalesce(s.is_closed, false) = false and coalesce(d.amount, 0) > 0 then 'P1_active_value'
        when d.hs_is_closed_won then 'P2_closed_won_history'
        else 'P3_other'
    end as review_priority,
    concat_ws('; ',
        case when coalesce(trim(d.hubspot_deal_source), '') = '' then 'missing_deal_source' end,
        case when coalesce(dc.direct_company_count, 0) = 0 then 'missing_direct_company_association' end
    ) as remediation_reasons
from deals d
left join direct_companies dc on d.deal_id = dc.deal_id
left join stages s on d.pipeline = s.pipeline_id and d.dealstage = s.stage_id
where (coalesce(s.is_closed, false) = false or d.hs_is_closed_won)
  and (
      coalesce(trim(d.hubspot_deal_source), '') = ''
      or coalesce(dc.direct_company_count, 0) = 0
  )
order by
    case
        when coalesce(s.is_closed, false) = false and coalesce(d.amount, 0) > 0 then 1
        when d.hs_is_closed_won then 2
        else 3
    end,
    d.amount desc nulls last,
    d.deal_id
