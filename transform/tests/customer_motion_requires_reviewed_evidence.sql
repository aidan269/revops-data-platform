-- Never classify a motion from company history or other inference.
select deal_id, customer_motion, customer_motion_evidence_status
from {{ ref('fct_customer_motion_live') }}
where customer_motion <> 'unclassified'
  and customer_motion_evidence_status <> 'reviewed_override'
