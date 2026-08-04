-- bridge_deal_contact — links deals to contacts for channel attribution.
-- One row per deal-contact association (latest snapshot).
-- Source: analytics_analytics.stg_deal_contacts

select
    dc.deal_id,
    dc.contact_id,
    dc.extracted_at
from {{ ref('stg_deal_contacts') }} dc
