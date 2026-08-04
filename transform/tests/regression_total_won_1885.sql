-- Regression guard: total hs_is_closed_won across all channels = 1885.
-- If this drifts, the mapping or extract changed. Fail loudly.
{{ config(store_failures = true) }}

select 'total_closed_won_mismatch' as test_name,
       sum(closed_won) as actual,
       1885 as expected
from {{ ref('mart_channel_performance') }}
having sum(closed_won) != 1885
