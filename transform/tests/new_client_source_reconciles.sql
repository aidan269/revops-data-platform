-- Source reporting must include exactly the reviewed net-new ARR population.
with detail as (
    select count(*) as deals, coalesce(sum(classified_arr_amount), 0) as amount
    from {{ ref('fct_customer_motion_live') }}
    where customer_motion = 'net_new_arr'
      and customer_motion_evidence_status = 'reviewed_override'
),
source_report as (
    select coalesce(sum(new_client_deals), 0) as deals,
           coalesce(sum(new_client_arr_amount), 0) as amount
    from {{ ref('mart_new_client_source_live') }}
)
select source_report.deals, detail.deals, source_report.amount, detail.amount
from source_report cross join detail
where source_report.deals != detail.deals
   or abs(source_report.amount - detail.amount) > 0.01
