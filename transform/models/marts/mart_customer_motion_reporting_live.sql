-- Investor reporting by customer motion and evidence status. The category
-- scaffold keeps the three requested ARR motions visible even when no reviewed
-- evidence exists and their measurable result is zero.

with motion_categories(customer_motion, reporting_label, display_order) as (
    values
        ('net_new_arr', 'Brand-new client ARR', 1),
        ('audit_to_arr_conversion', 'Audit-to-ARR conversion', 2),
        ('expansion', 'Expansion ARR', 3),
        ('renewal', 'Renewal', 4),
        ('other_non_arr', 'Other / non-ARR', 5),
        ('unclassified', 'Unclassified', 6)
),
evidence_rollup as (
    select
        customer_motion,
        customer_motion_evidence_status,
        count(*) as deal_count,
        coalesce(sum(closed_won_deal_amount), 0) as closed_won_deal_amount,
        coalesce(sum(classified_arr_amount), 0) as classified_arr_amount
    from {{ ref('fct_customer_motion_live') }}
    group by 1, 2
),
totals as (
    select
        count(*) as total_live_closed_won_deals,
        coalesce(sum(closed_won_deal_amount), 0) as total_live_closed_won_deal_amount,
        count(*) filter (where customer_motion <> 'unclassified') as reviewed_deals,
        coalesce(sum(closed_won_deal_amount) filter (where customer_motion <> 'unclassified'), 0)
            as reviewed_deal_amount
    from {{ ref('fct_customer_motion_live') }}
),
report_rows as (
    select
        c.customer_motion,
        c.reporting_label,
        c.display_order,
        coalesce(e.customer_motion_evidence_status, 'no_reviewed_records') as evidence_status,
        coalesce(e.deal_count, 0) as deal_count,
        coalesce(e.closed_won_deal_amount, 0) as closed_won_deal_amount,
        coalesce(e.classified_arr_amount, 0) as classified_arr_amount
    from motion_categories c
    left join evidence_rollup e on c.customer_motion = e.customer_motion
)

select
    r.customer_motion,
    r.reporting_label,
    r.evidence_status,
    case
        when r.customer_motion in ('net_new_arr', 'audit_to_arr_conversion', 'expansion')
             and r.deal_count = 0 then 'not_yet_measurable_no_reviewed_evidence'
        when r.customer_motion = 'unclassified' then 'classification_required'
        else 'measurable_from_reviewed_evidence'
    end as measurement_status,
    r.deal_count,
    r.closed_won_deal_amount,
    r.classified_arr_amount,
    t.total_live_closed_won_deals,
    t.total_live_closed_won_deal_amount,
    t.reviewed_deals,
    t.reviewed_deal_amount,
    round(100.0 * t.reviewed_deals / nullif(t.total_live_closed_won_deals, 0), 2)
        as reviewed_deal_coverage_pct,
    round(100.0 * t.reviewed_deal_amount / nullif(t.total_live_closed_won_deal_amount, 0), 2)
        as reviewed_amount_coverage_pct,
    r.display_order
from report_rows r
cross join totals t
order by r.display_order, r.evidence_status
