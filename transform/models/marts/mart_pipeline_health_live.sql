-- Current, live-only pipeline health with human-readable HubSpot stage names.

with deals as (
    select * from {{ ref('mart_gtm_lifecycle_live') }}
),
stages as (
    select * from {{ ref('stg_hubspot_deal_stages') }}
)

select
    coalesce(s.pipeline_label, d.pipeline, 'Unmapped pipeline') as pipeline_name,
    coalesce(s.stage_label, d.dealstage, 'Unmapped stage') as stage_name,
    d.pipeline as pipeline_id,
    d.dealstage as stage_id,
    s.display_order,
    s.probability,
    s.is_closed,
    count(*) as deals,
    coalesce(sum(d.amount), 0) as pipeline_amount,
    count(*) filter (where coalesce(trim(d.hubspot_deal_source), '') = '') as blank_deal_source,
    count(*) filter (where d.company_id is null) as unassociated_company,
    count(*) filter (where d.primary_contact_email is null) as no_primary_contact
from deals d
left join stages s
    on d.pipeline = s.pipeline_id
   and d.dealstage = s.stage_id
group by 1, 2, 3, 4, 5, 6, 7
order by pipeline_name, display_order nulls last, stage_name
