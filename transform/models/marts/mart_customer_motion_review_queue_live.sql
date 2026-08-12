-- Durable, read-only queue for live closed-won deals lacking reviewed motion.

select
    deal_id,
    closed_won_deal_amount,
    deal_createdate,
    deal_closedate,
    company_id,
    company_name,
    live_company_history_lifecycle,
    live_first_known_company_win_date,
    live_closed_won_deals_for_company,
    hubspot_deal_source,
    first_touch_channel,
    first_touch_utm_source,
    attribution_evidence_status,
    customer_motion_evidence_status,
    case
        when company_id is null then
            'Confirm the direct company association, then review contract and product/service lineage.'
        when live_company_history_lifecycle = 'first_known_company_win' then
            'Review signed contract and Finance ARR schedule; confirm net-new ARR versus non-ARR work.'
        when live_company_history_lifecycle = 'repeat_company_win' then
            'Compare prior and current contracts/service lines; classify only with explicit audit-conversion, expansion, renewal, or non-ARR evidence.'
        else
            'Review contract, product/service lineage, and Finance ARR schedule.'
    end as recommended_reviewer_action,
    'Do not classify from company history alone. Add a reviewed row to gtm_deal_motion_overrides with evidence.' as classification_guardrail
from {{ ref('fct_customer_motion_live') }}
where customer_motion = 'unclassified'
order by closed_won_deal_amount desc nulls last, deal_id
