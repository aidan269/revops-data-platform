-- Permanent, read-only reconstruction of the 621-deal Deal Source backfill.
--
-- The cohort is identified by the approved first-touch-to-source mapping and
-- the matching current Deal Source in the latest warehouse extract. This model
-- reads warehouse data only and never calls or writes to HubSpot.

with expected_sources as (
    select
        deal_id,
        hubspot_deal_source as current_deal_source,
        first_touch_channel,
        first_touch_utm_source,
        utm_quality,
        attribution_evidence_status,
        case
            when first_touch_channel = 'Google Ads' then 'Paid Search'
            when first_touch_channel in ('Direct', 'Webflow / Cantina') then 'Website / Direct'
            when first_touch_channel = 'Email / In-app' then 'Email / Nurture'
            when first_touch_channel = 'Organic Search' then 'Organic Search'
        end as expected_deal_source
    from {{ ref('mart_gtm_lifecycle_live') }}
    where first_touch_channel in (
        'Google Ads', 'Direct', 'Webflow / Cantina', 'Email / In-app', 'Organic Search'
    )
)

select
    deal_id,
    current_deal_source,
    first_touch_channel,
    first_touch_utm_source,
    utm_quality,
    attribution_evidence_status,
    concat_ws('; ',
        'channel=' || first_touch_channel,
        'utm_source=' || coalesce(first_touch_utm_source, 'missing'),
        'utm_quality=' || coalesce(utm_quality, 'missing'),
        'evidence_status=' || attribution_evidence_status
    ) as first_touch_evidence,
    'Reconstructed from the current warehouse; the original generated audit CSV was removed.' as audit_note
from expected_sources
where current_deal_source = expected_deal_source
order by deal_id
