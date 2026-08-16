-- mart_icp_fit_score — deterministic, explainable ICP-fit score on open pipeline.
-- Scores open deals against the won-account profile (from int_won_accounts).
-- The score is a weighted match — no black box. Weights are transparent and
-- documented below.
--
-- Score components (each 0 or 1, weighted):
--   industry_match:     25 pts — does this deal's industry match a top-3 won industry?
--   employee_range_match: 20 pts — does the employee range match the mid-market sweet spot (201-500, 1001-5000)?
--   seniority_match:   20 pts — is the contact seniority in the decision-maker set (executive, vp, director)?
--   channel_match:     15 pts — is the acquisition channel in the top-3 by win rate (Referral, Email, Organic)?
--   deal_size_match:   10 pts — is the deal size in the won-deal sweet spot ($10k-$50k)?
--   days_to_close:     10 pts — has the deal been open < 120 days (within the avg close window)?
--
-- Max score = 100. A deal scoring 70+ is a strong fit.
--
-- Sources:
--   analytics_analytics.dim_deal (open deals — hs_is_closed_won = false, dealstage != closedlost)
--   analytics_analytics.dim_contact (firmographics)
--   analytics_analytics.int_contact_channel (channel)
--   analytics_analytics.int_won_accounts (won profile for thresholds)

with won_profile as (
    select * from {{ ref('int_won_accounts') }}
),

-- Derive ICP thresholds from won accounts
won_thresholds as (
    select
        -- Top 3 industries by won count
        (array_agg(industry order by cnt desc))[1:3] as top_industries,
        -- Mid-market employee ranges
        array['201-500', '1001-5000'] as mid_market_ranges,
        -- Decision-maker seniorities
        array['executive', 'vp', 'director'] as decision_maker_seniorities,
        -- Top 3 channels by win rate (from Task 4: Referral, Email, Organic)
        array['Referral / Partner', 'Email / In-app', 'Organic Search'] as top_channels,
        -- Deal size sweet spot
        10000 as min_deal_size,
        50000 as max_deal_size,
        -- Avg days to close
        round(avg(days_to_close), 0) as avg_days_to_close
    from (
        select industry, count(*) as cnt
        from won_profile
        where industry is not null and industry != ''
        group by industry
        order by cnt desc
        limit 3
    ) t
    cross join (
        select avg(days_to_close) as days_to_close from won_profile
    ) d
),

open_deal_candidates as (
    select
        d.deal_id,
        d.amount,
        d.createdate,
        dc.contact_id,
        c.company_id,
        c.company_name,
        c.industry,
        c.hs_employee_range,
        c.hs_seniority,
        c.numberofemployees,
        ch.channel as acquisition_channel,
        extract(epoch from (now() - d.createdate)) / 86400 as days_open,
        row_number() over (
            partition by d.deal_id
            order by c.createdate nulls last, dc.contact_id
        ) as contact_rank
    from {{ ref('dim_deal') }} d
    inner join {{ ref('bridge_deal_contact') }} dc on d.deal_id = dc.deal_id
    inner join {{ ref('dim_contact') }} c on dc.contact_id = c.contact_id
    inner join {{ ref('int_contact_channel') }} ch on dc.contact_id = ch.contact_id
    where d.hs_is_closed_won = false
      and d.dealstage != 'closedlost'
),
open_deals as (
    select * from open_deal_candidates where contact_rank = 1
)

select
    od.deal_id,
    od.amount,
    od.company_name,
    od.industry,
    od.hs_employee_range,
    od.hs_seniority,
    od.acquisition_channel,
    round(od.days_open, 0) as days_open,

    -- ICP-fit score (max 100, explainable)
    -- 25 pts: industry match
    case when od.industry = any(wt.top_industries) then 25 else 0 end
    -- 20 pts: employee range match
    + case when od.hs_employee_range = any(wt.mid_market_ranges) then 20 else 0 end
    -- 20 pts: seniority match
    + case when od.hs_seniority = any(wt.decision_maker_seniorities) then 20 else 0 end
    -- 15 pts: channel match
    + case when od.acquisition_channel = any(wt.top_channels) then 15 else 0 end
    -- 10 pts: deal size match
    + case when od.amount >= wt.min_deal_size and od.amount <= wt.max_deal_size then 10 else 0 end
    -- 10 pts: days open within close window
    + case when od.days_open <= 120 then 10 else 0 end
    as icp_fit_score,

    -- Score breakdown (explainable)
    case when od.industry = any(wt.top_industries) then 25 else 0 end as pts_industry,
    case when od.hs_employee_range = any(wt.mid_market_ranges) then 20 else 0 end as pts_employee_range,
    case when od.hs_seniority = any(wt.decision_maker_seniorities) then 20 else 0 end as pts_seniority,
    case when od.acquisition_channel = any(wt.top_channels) then 15 else 0 end as pts_channel,
    case when od.amount >= wt.min_deal_size and od.amount <= wt.max_deal_size then 10 else 0 end as pts_deal_size,
    case when od.days_open <= 120 then 10 else 0 end as pts_days_open,

    -- Coverage caveats
    (od.hs_seniority is null or od.hs_seniority = '') as missing_seniority,
    (od.industry is null or od.industry = '') as missing_industry,
    (od.hs_employee_range is null or od.hs_employee_range = '') as missing_employee_range

from open_deals od
cross join won_thresholds wt
order by icp_fit_score desc
