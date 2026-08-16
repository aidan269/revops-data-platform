-- Legacy filename retained. A changing warehouse cannot use a frozen fixture
-- count; enforce the durable per-channel funnel invariant instead.
{{ config(store_failures = true) }}

select channel, deals_created, closed_won
from {{ ref('mart_channel_performance') }}
where closed_won > deals_created
