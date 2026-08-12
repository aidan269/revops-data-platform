-- Acquisition source for explicitly reviewed brand-new client ARR only.
-- An empty result means source performance is not yet measurable.

select
    coalesce(first_touch_channel, 'Unknown / missing evidence') as acquisition_channel,
    attribution_evidence_status,
    count(*) as new_client_deals,
    coalesce(sum(classified_arr_amount), 0) as new_client_arr_amount
from {{ ref('fct_customer_motion_live') }}
where customer_motion = 'net_new_arr'
  and customer_motion_evidence_status = 'reviewed_override'
group by 1, 2
order by new_client_arr_amount desc, acquisition_channel
