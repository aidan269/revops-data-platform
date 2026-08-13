-- Investor-safe coverage by UTM quality and form-evidence status.

with totals as (
    select count(*) as total_live_deals
    from {{ ref('fct_web_attribution_readiness_live') }}
)
select
    f.utm_evidence_status,
    f.web_form_evidence_status,
    f.website_click_evidence_status,
    f.bot_junk_signal_status,
    count(*) as live_deals,
    count(*) filter (where f.hs_is_closed_won) as live_closed_won_deals,
    coalesce(sum(f.deal_amount), 0) as live_deal_amount,
    coalesce(sum(f.deal_amount) filter (where f.hs_is_closed_won), 0) as live_closed_won_amount,
    sum(f.predeal_form_submission_count) as predeal_form_submissions,
    round(100.0 * count(*) / nullif(t.total_live_deals, 0), 2) as live_deal_coverage_pct
from {{ ref('fct_web_attribution_readiness_live') }} f
cross join totals t
group by 1, 2, 3, 4, t.total_live_deals
order by 1, 2
