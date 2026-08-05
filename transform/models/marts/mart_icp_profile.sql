-- mart_icp_profile — profiles won vs open vs lost accounts across key dimensions.
-- Surfaces where won accounts concentrate (the ICP signal) and where they diverge from lost.
--
-- Dimensions: industry, employee_range, hs_seniority, acquisition_channel,
-- deal_size_band, days_to_close_band.
--
-- For each dimension value, reports:
--   won_count, open_count, lost_count, win_rate, won_amount, avg_days_to_close
--
-- Sources:
--   analytics_analytics.int_won_accounts (won)
--   analytics_analytics.dim_deal + bridge_deal_contact + dim_contact + int_contact_channel (all)

with all_deals as (
    select
        d.deal_id,
        d.amount,
        d.hs_is_closed_won,
        d.dealstage,
        d.createdate,
        d.closedate,
        dc.contact_id,
        c.industry,
        c.hs_employee_range,
        c.hs_seniority,
        c.numberofemployees,
        ch.channel as acquisition_channel,
        case
            when d.amount < 10000 then '<$10k'
            when d.amount < 25000 then '$10k-$25k'
            when d.amount < 50000 then '$25k-$50k'
            when d.amount < 100000 then '$50k-$100k'
            else '$100k+'
        end as deal_size_band,
        case
            when d.hs_is_closed_won and d.closedate is not null
            then extract(epoch from (d.closedate - d.createdate)) / 86400
            else null
        end as days_to_close
    from {{ ref('dim_deal') }} d
    inner join {{ ref('bridge_deal_contact') }} dc on d.deal_id = dc.deal_id
    inner join {{ ref('dim_contact') }} c on dc.contact_id = c.contact_id
    inner join {{ ref('int_contact_channel') }} ch on dc.contact_id = ch.contact_id
),

-- Profile by industry
industry_profile as (
    select
        'industry' as dimension,
        coalesce(industry, 'Unknown') as dimension_value,
        count(*) as total_deals,
        count(case when hs_is_closed_won then 1 end) as won_count,
        count(case when hs_is_closed_won = false and dealstage != 'closedlost' then 1 end) as open_count,
        count(case when hs_is_closed_won = false and dealstage = 'closedlost' then 1 end) as lost_count,
        coalesce(sum(case when hs_is_closed_won then amount else 0 end), 0) as won_amount,
        round(avg(case when hs_is_closed_won then days_to_close end), 1) as avg_days_to_close
    from all_deals
    group by coalesce(industry, 'Unknown')
),

-- Profile by employee range
emp_range_profile as (
    select
        'employee_range' as dimension,
        coalesce(hs_employee_range, 'Unknown') as dimension_value,
        count(*) as total_deals,
        count(case when hs_is_closed_won then 1 end) as won_count,
        count(case when hs_is_closed_won = false and dealstage != 'closedlost' then 1 end) as open_count,
        count(case when hs_is_closed_won = false and dealstage = 'closedlost' then 1 end) as lost_count,
        coalesce(sum(case when hs_is_closed_won then amount else 0 end), 0) as won_amount,
        round(avg(case when hs_is_closed_won then days_to_close end), 1) as avg_days_to_close
    from all_deals
    group by coalesce(hs_employee_range, 'Unknown')
),

-- Profile by seniority
seniority_profile as (
    select
        'seniority' as dimension,
        coalesce(hs_seniority, 'Unknown') as dimension_value,
        count(*) as total_deals,
        count(case when hs_is_closed_won then 1 end) as won_count,
        count(case when hs_is_closed_won = false and dealstage != 'closedlost' then 1 end) as open_count,
        count(case when hs_is_closed_won = false and dealstage = 'closedlost' then 1 end) as lost_count,
        coalesce(sum(case when hs_is_closed_won then amount else 0 end), 0) as won_amount,
        round(avg(case when hs_is_closed_won then days_to_close end), 1) as avg_days_to_close
    from all_deals
    group by coalesce(hs_seniority, 'Unknown')
),

-- Profile by acquisition channel
channel_profile as (
    select
        'acquisition_channel' as dimension,
        acquisition_channel as dimension_value,
        count(*) as total_deals,
        count(case when hs_is_closed_won then 1 end) as won_count,
        count(case when hs_is_closed_won = false and dealstage != 'closedlost' then 1 end) as open_count,
        count(case when hs_is_closed_won = false and dealstage = 'closedlost' then 1 end) as lost_count,
        coalesce(sum(case when hs_is_closed_won then amount else 0 end), 0) as won_amount,
        round(avg(case when hs_is_closed_won then days_to_close end), 1) as avg_days_to_close
    from all_deals
    group by acquisition_channel
),

-- Profile by deal size band
deal_size_profile as (
    select
        'deal_size_band' as dimension,
        deal_size_band as dimension_value,
        count(*) as total_deals,
        count(case when hs_is_closed_won then 1 end) as won_count,
        count(case when hs_is_closed_won = false and dealstage != 'closedlost' then 1 end) as open_count,
        count(case when hs_is_closed_won = false and dealstage = 'closedlost' then 1 end) as lost_count,
        coalesce(sum(case when hs_is_closed_won then amount else 0 end), 0) as won_amount,
        round(avg(case when hs_is_closed_won then days_to_close end), 1) as avg_days_to_close
    from all_deals
    group by deal_size_band
)

-- Union all profiles
select * from industry_profile
union all
select * from emp_range_profile
union all
select * from seniority_profile
union all
select * from channel_profile
union all
select * from deal_size_profile
order by dimension, won_count desc
