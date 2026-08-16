-- Bot/junk classification is prohibited without a deterministic source field.
select deal_id, bot_junk_signal_status
from {{ ref('fct_web_attribution_readiness_live') }}
where bot_junk_signal_status <> 'not_assessable_no_deterministic_fields'
