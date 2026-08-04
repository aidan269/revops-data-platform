-- dim_company — one row per company (latest snapshot).
-- Source: analytics_analytics.stg_hubspot_companies

select
    company_id,
    company_name,
    domain,
    industry,
    numberofemployees,
    hs_employee_range,
    extracted_at
from {{ ref('stg_hubspot_companies') }}
