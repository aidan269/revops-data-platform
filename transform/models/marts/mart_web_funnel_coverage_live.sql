-- Coverage checkpoints for the measurable live-deal attribution chain.

with f as (
    select * from {{ ref('fct_web_attribution_readiness_live') }}
),
stage_definitions as (
    select 1 as stage_order, 'live_deal_population' as funnel_stage, 'available_live_only' as evidence_status
    union all select 2, 'associated_contact', 'available'
    union all select 3, 'predeal_form_evidence', 'available_when_contact_linked'
    union all select 4, 'clean_first_touch_utm', 'available_when_captured'
    union all select 5, 'predeal_form_plus_clean_utm', 'available_when_both_captured'
    union all select 6, 'predeal_form_plus_clean_utm_closed_won', 'available_live_only'
    union all select 7, 'website_click_evidence', 'unavailable_not_collected'
),
stage_rows as (
    select
        d.*,
        f.*,
        case d.stage_order
            when 1 then true
            when 2 then f.associated_contact_count > 0
            when 3 then f.predeal_form_submission_count > 0
            when 4 then f.utm_evidence_status = 'clean_utm'
            when 5 then f.predeal_form_submission_count > 0 and f.utm_evidence_status = 'clean_utm'
            when 6 then f.predeal_form_submission_count > 0
                        and f.utm_evidence_status = 'clean_utm' and f.hs_is_closed_won
            when 7 then f.has_website_click_evidence
        end as include_row
    from stage_definitions d
    cross join f
),
totals as (
    select count(*) as live_deals from f
)
select
    s.stage_order,
    s.funnel_stage,
    s.evidence_status,
    count(*) filter (where s.include_row) as deal_count,
    count(*) filter (where s.include_row and s.hs_is_closed_won) as closed_won_deal_count,
    coalesce(sum(s.deal_amount) filter (where s.include_row), 0) as deal_amount,
    coalesce(sum(s.deal_amount) filter (where s.include_row and s.hs_is_closed_won), 0)
        as closed_won_amount,
    round(100.0 * count(*) filter (where s.include_row) / nullif(t.live_deals, 0), 2)
        as coverage_of_live_deals_pct
from stage_rows s
cross join totals t
group by 1, 2, 3, t.live_deals
order by s.stage_order
