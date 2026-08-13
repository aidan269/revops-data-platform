-- Investor-facing, live-only closed-won customer-motion detail.
-- A deal receives an ARR motion only through a reviewed override. Company deal
-- history is evidence for review, never classification evidence by itself.

with live_closed_won as (
    select *
    from {{ ref('mart_gtm_lifecycle_live') }}
    where hs_is_closed_won = true
),
live_history as (
    select
        *,
        min(deal_closedate) over (partition by company_id) as live_first_known_company_win_date,
        count(*) over (partition by company_id) as live_closed_won_deals_for_company
    from live_closed_won
)

select
    deal_id,
    amount as closed_won_deal_amount,
    deal_createdate,
    deal_closedate,
    pipeline,
    dealstage,
    company_id,
    company_name,
    contact_id,
    primary_contact_email,
    hubspot_deal_source,
    first_touch_channel,
    first_touch_utm_source,
    utm_quality,
    attribution_evidence_status,
    live_first_known_company_win_date,
    live_closed_won_deals_for_company,
    case
        when company_id is null then 'unmapped_company'
        when deal_closedate = live_first_known_company_win_date then 'first_known_company_win'
        else 'repeat_company_win'
    end as live_company_history_lifecycle,
    customer_motion,
    customer_motion_evidence_status,
    customer_motion_evidence_note,
    reviewed_by,
    reviewed_at,
    case
        when customer_motion in ('net_new_arr', 'audit_to_arr_conversion', 'expansion')
            then amount
    end as classified_arr_amount,
    case
        when customer_motion = 'net_new_arr' then first_touch_channel
    end as new_client_acquisition_channel,
    modeled_at
from live_history
