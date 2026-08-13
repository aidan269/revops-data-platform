-- One row per live deal with only deterministic web/marketing evidence.
-- Website clicks are explicitly unavailable: email_click is not relabeled.

with live_deals as (
    select * from {{ ref('mart_gtm_lifecycle_live') }}
),
form_events as (
    select
        engagement_id,
        contact_id,
        "timestamp" as event_timestamp,
        campaign_id
    from {{ ref('stg_hubspot_engagements') }}
    where engagement_type = 'form_submission'
),
deal_contact_evidence as (
    select
        d.deal_id,
        count(distinct dc.contact_id) as associated_contact_count,
        count(distinct f.engagement_id) as form_submission_count,
        count(distinct f.engagement_id) filter (
            where f.event_timestamp <= d.deal_createdate
        ) as predeal_form_submission_count,
        count(distinct f.engagement_id) filter (
            where f.event_timestamp > d.deal_createdate
        ) as postdeal_form_submission_count,
        count(distinct f.campaign_id) filter (
            where f.event_timestamp <= d.deal_createdate
        ) as predeal_form_campaign_count
    from live_deals d
    left join {{ ref('bridge_deal_contact') }} dc on d.deal_id = dc.deal_id
    left join form_events f on dc.contact_id = f.contact_id
    group by 1
)

select
    d.deal_id,
    d.deal_createdate,
    d.deal_closedate,
    d.hs_is_closed_won,
    d.amount as deal_amount,
    d.contact_id as primary_contact_id,
    coalesce(e.associated_contact_count, 0) as associated_contact_count,
    coalesce(e.form_submission_count, 0) as form_submission_count,
    coalesce(e.predeal_form_submission_count, 0) as predeal_form_submission_count,
    coalesce(e.postdeal_form_submission_count, 0) as postdeal_form_submission_count,
    coalesce(e.predeal_form_campaign_count, 0) as predeal_form_campaign_count,
    false as has_website_click_evidence,
    'unavailable_not_collected' as website_click_evidence_status,
    case
        when coalesce(e.associated_contact_count, 0) = 0 then 'unavailable_no_associated_contact'
        when coalesce(e.predeal_form_submission_count, 0) > 0 then 'predeal_form_evidence'
        when coalesce(e.postdeal_form_submission_count, 0) > 0 then 'form_evidence_after_deal_only'
        else 'no_form_evidence'
    end as web_form_evidence_status,
    d.first_touch_channel,
    d.first_touch_utm_source,
    d.utm_quality,
    case
        when coalesce(e.associated_contact_count, 0) = 0 or d.contact_id is null
            then 'unavailable_no_associated_contact'
        when d.utm_quality = 'clean' then 'clean_utm'
        when d.utm_quality = 'corrupted' then 'corrupted_utm'
        else 'missing_or_inferred_utm'
    end as utm_evidence_status,
    'not_assessable_no_deterministic_fields' as bot_junk_signal_status,
    'No user agent, IP classification, CAPTCHA result, spam disposition, or equivalent deterministic signal is available.'
        as bot_junk_evidence_note
from live_deals d
left join deal_contact_evidence e on d.deal_id = e.deal_id
