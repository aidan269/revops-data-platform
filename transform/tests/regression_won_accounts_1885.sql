-- Legacy filename retained to preserve repository history. The warehouse has
-- moved beyond the old 1,885-row fixture, so reconcile to the canonical model
-- instead of freezing a source population that legitimately changes.
{{ config(store_failures = true) }}

with actual as (
    select count(*) as deal_count
    from {{ ref('int_won_accounts') }}
),
expected as (
    select count(*) as deal_count
    from {{ ref('dim_deal') }}
    where hs_is_closed_won = true
)

select
    'won_account_count_mismatch' as test_name,
    actual.deal_count as actual,
    expected.deal_count as expected
from actual
cross join expected
where actual.deal_count != expected.deal_count
