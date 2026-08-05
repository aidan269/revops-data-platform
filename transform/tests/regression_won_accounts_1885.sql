-- Regression guard: int_won_accounts reconciles to ~1,885 closed-won deals.
-- If this fails, the won-account cohort diverged from the known HubSpot count.
{{ config(store_failures = true) }}

select 'won_account_count_mismatch' as test_name,
       count(*) as actual,
       1885 as expected
from {{ ref('int_won_accounts') }}
having count(*) != 1885
