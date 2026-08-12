-- Durable inventory of warehouse evidence and its investor-reporting scope.

select 'website_page_view' as evidence_type, 'unavailable' as availability,
       'none' as available_fields, 'not_measurable' as reporting_scope,
       0::bigint as record_count
union all
select 'website_click', 'unavailable', 'none; email_click is a different event',
       'not_measurable', 0::bigint
union all
select 'form_submission', 'available',
       'engagement_id, contact_id, timestamp, campaign_id',
       'contact_linked; investor claims only after linkage to a live deal', count(*)
from {{ ref('stg_hubspot_engagements') }} where engagement_type = 'form_submission'
union all
select 'contact_utm', 'available', 'utm_source, utm_medium, utm_campaign',
       'contact_linked; quality explicitly classified', count(*)
from {{ ref('stg_hubspot_contacts') }}
union all
select 'campaign', 'available', 'campaign_id, name, type',
       'contact/engagement linked when IDs are populated', count(*)
from {{ ref('stg_hubspot_campaigns') }}
union all
select 'live_deal_and_win', 'available',
       'deal_id, contact association, amount, created date, close date, closed-won flag',
       'live_only; development fixtures excluded', count(*)
from {{ ref('mart_gtm_lifecycle_live') }}
union all
select 'bot_or_junk_signal', 'unavailable',
       'no user agent, IP classification, CAPTCHA result, or spam disposition',
       'not_assessable_without_deterministic_evidence', 0::bigint
