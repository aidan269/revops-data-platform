-- A pre-deal form label requires at least one form at or before deal creation.
select deal_id, web_form_evidence_status, predeal_form_submission_count
from {{ ref('fct_web_attribution_readiness_live') }}
where (web_form_evidence_status = 'predeal_form_evidence' and predeal_form_submission_count = 0)
   or (web_form_evidence_status <> 'predeal_form_evidence' and predeal_form_submission_count > 0)
