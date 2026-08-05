-- int_won_accounts — one row per closed-won account (deal) with firmographics,
-- acquisition channel, primary-contact seniority, days-to-close, and deal amount.
-- Also carries enrichment coverage flags so every ICP claim discloses its data backing.
--
-- Reconciles to ~1,885 closed-won deals (hs_is_closed_won = true).
--
-- Sources:
--   analytics_analytics.dim_deal (deal facts, hs_is_closed_won)
--   analytics_analytics.bridge_deal_contact (deal→contact)
--   analytics_analytics.dim_contact (firmographics via company association)
--   analytics_analytics.int_contact_channel (acquisition channel)
--   analytics_analytics.mart_enrichment_gaps (coverage flags)

with deals as (
    select * from {{ ref('dim_deal') }} where hs_is_closed_won = true
),
deal_contacts as (
    select * from {{ ref('bridge_deal_contact') }}
),
contacts as (
    select * from {{ ref('dim_contact') }}
),
channels as (
    select * from {{ ref('int_contact_channel') }}
),
gaps as (
    select * from {{ ref('mart_enrichment_gaps') }}
)

select
    d.deal_id,
    d.amount,
    d.createdate as deal_createdate,
    d.closedate as deal_closedate,
    extract(epoch from (d.closedate - d.createdate)) / 86400 as days_to_close,

    -- Contact + firmographics
    dc.contact_id,
    c.email,
    c.jobtitle,
    c.hs_seniority,
    c.company_id,
    c.company_name,
    c.industry,
    c.numberofemployees,
    c.hs_employee_range,

    -- Acquisition channel (first-touch)
    ch.channel as acquisition_channel,
    ch.utm_source,

    -- Enrichment coverage flags (from mart_enrichment_gaps)
    g.gap_hs_seniority,
    g.gap_industry,
    g.gap_hs_employee_range
from deals d
inner join deal_contacts dc on d.deal_id = dc.deal_id
inner join contacts c on dc.contact_id = c.contact_id
inner join channels ch on dc.contact_id = ch.contact_id
left join gaps g on dc.contact_id = g.contact_id
