-- Regression guard: Unknown (corrupted UTM) bucket = 138 contacts.
-- The 138-row corruption must always show as exactly 138. If this drifts, fail loudly.
{{ config(store_failures = true) }}

select 'corrupted_utm_bucket_mismatch' as test_name,
       contacts as actual,
       138 as expected
from {{ ref('mart_channel_performance') }}
where channel = 'Unknown (corrupted UTM)'
  and contacts != 138
