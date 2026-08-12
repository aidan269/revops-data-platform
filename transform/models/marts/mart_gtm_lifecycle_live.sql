-- mart_gtm_lifecycle_live — the diligence-safe view of current HubSpot deals.
--
-- The repository contains historical mock fixtures for development. This model
-- deliberately retains only IDs seen in a recent live HubSpot deals extract,
-- so demos/fixtures cannot inflate a CRM or investor-facing report.

with current_live_deal_ids as (
    select distinct on (id) id
    from {{ source('raw', 'hubspot_deals') }}
    where extracted_at >= current_timestamp - interval '7 days'
      -- Development fixtures use six-digit IDs (for example 300000).
      -- Current HubSpot deal IDs in this portal are eight or more digits.
      and id ~ '^[0-9]{8,}$'
    order by id, extracted_at desc
)

select m.*
from {{ ref('mart_gtm_lifecycle') }} m
inner join current_live_deal_ids live
    on live.id = m.deal_id
