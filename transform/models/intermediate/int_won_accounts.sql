-- int_won_accounts — one row per closed-won account (deal) with firmographics,
-- acquisition channel, primary-contact seniority, days-to-close, and deal amount.
-- Also carries enrichment coverage flags so every ICP claim discloses its data backing.
--
-- Reconciles exactly to the current distinct closed-won deals in dim_deal.
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
),
deal_contact_candidates as (
    select
        d.deal_id,
        d.amount,
        d.createdate as deal_createdate,
        d.closedate as deal_closedate,
        dc.contact_id,
        c.email,
        c.jobtitle,
        c.hs_seniority,
        c.company_id,
        c.company_name,
        c.industry,
        c.numberofemployees,
        c.hs_employee_range,
        ch.channel as acquisition_channel,
        ch.utm_source,
        g.gap_hs_seniority,
        g.gap_industry,
        g.gap_hs_employee_range,
        row_number() over (
            partition by d.deal_id
            order by c.createdate nulls last, dc.contact_id nulls last
        ) as contact_rank
    from deals d
    left join deal_contacts dc on d.deal_id = dc.deal_id
    left join contacts c on dc.contact_id = c.contact_id
    left join channels ch on dc.contact_id = ch.contact_id
    left join gaps g on dc.contact_id = g.contact_id
)

select
    deal_id,
    amount,
    deal_createdate,
    deal_closedate,
    extract(epoch from (deal_closedate - deal_createdate)) / 86400 as days_to_close,

    -- Contact + firmographics
    contact_id,
    email,
    jobtitle,
    hs_seniority,
    company_id,
    company_name,
    industry,
    numberofemployees,
    hs_employee_range,

    -- Acquisition channel (first-touch)
    acquisition_channel,
    utm_source,

    -- Enrichment coverage flags (from mart_enrichment_gaps)
    gap_hs_seniority,
    gap_industry,
    gap_hs_employee_range
from deal_contact_candidates
where contact_rank = 1
