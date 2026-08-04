-- mart_enrichment_gaps — one row per contact with boolean gap flags per target field.
-- This is what the CRM-enrichment job reads to decide which fields to fill.
-- Gap = true means the field is empty/null and needs enrichment.
--
-- Target fields (from crm_enrichment.md):
--   hs_seniority (baseline: 1.4% filled)
--   industry (baseline: 68% filled)
--   hs_employee_range (baseline: 21% filled)
--
-- Source: analytics_analytics.dim_contact

select
    contact_id,
    email,
    jobtitle,
    hs_seniority,
    company_name,
    industry,
    hs_employee_range,
    -- Gap flags: true = field is empty/missing → needs enrichment
    (hs_seniority IS NULL OR hs_seniority = '')    AS gap_hs_seniority,
    (industry IS NULL OR industry = '')            AS gap_industry,
    (hs_employee_range IS NULL OR hs_employee_range = '') AS gap_hs_employee_range,
    -- Combined: any gap at all
    (
        (hs_seniority IS NULL OR hs_seniority = '')
        OR (industry IS NULL OR industry = '')
        OR (hs_employee_range IS NULL OR hs_employee_range = '')
    ) AS has_any_gap
from {{ ref('dim_contact') }}
