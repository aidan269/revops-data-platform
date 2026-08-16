-- Legacy filename retained. Reconcile the refreshed corrupted-UTM bucket to
-- its canonical contact classification rather than a frozen fixture count.
{{ config(store_failures = true) }}

with expected as (
    select count(*) as contacts
    from {{ ref('int_contact_channel') }}
    where channel = 'Unknown (corrupted UTM)'
),
actual as (
    select contacts
    from {{ ref('mart_channel_performance') }}
    where channel = 'Unknown (corrupted UTM)'
)
select actual.contacts as actual, expected.contacts as expected
from actual cross join expected
where actual.contacts != expected.contacts
