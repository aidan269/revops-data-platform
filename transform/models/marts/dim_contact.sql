-- dim_contact — one row per contact (latest snapshot), enriched with company info.
-- This is what the CRM-enrichment job and Hermes read.
-- Source: analytics_analytics.stg_hubspot_contacts + stg_contact_company_map + stg_hubspot_companies

with contacts as (
    select * from {{ ref('stg_hubspot_contacts') }}
),
associations as (
    select * from {{ ref('stg_contact_company_map') }}
),
companies as (
    select * from {{ ref('stg_hubspot_companies') }}
)

select
    c.contact_id,
    c.email,
    c.jobtitle,
    c.hs_seniority,
    c.createdate,
    c.utm_source,
    c.utm_medium,
    c.utm_campaign,
    c.extracted_at,
    -- Company fields via association
    a.company_id,
    comp.company_name,
    comp.industry,
    comp.numberofemployees,
    comp.hs_employee_range
from contacts c
left join associations a
    on c.contact_id = a.contact_id
left join companies comp
    on a.company_id = comp.company_id
