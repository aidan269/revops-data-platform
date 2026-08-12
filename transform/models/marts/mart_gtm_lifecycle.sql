-- mart_gtm_lifecycle — canonical, auditable deal lifecycle and attribution spine.
--
-- The warehouse does not currently contain a product/service or Deal Source
-- property. This model therefore never guesses "audit conversion" or
-- "expansion". It labels the defensible company-history state, surfaces the
-- evidence gap, and accepts reviewed overrides from gtm_deal_motion_overrides.

with deal_contact_candidates as (
    select
        d.deal_id,
        d.amount,
        d.dealstage,
        d.pipeline,
        d.hs_is_closed_won,
        d.createdate as deal_createdate,
        d.closedate as deal_closedate,
        d.deal_source as hubspot_deal_source,
        d.original_traffic_source as hubspot_original_traffic_source,
        d.deal_owner_id,
        d.next_step,
        d.next_step_updated_at,
        d.product_service,
        d.billing_model,
        d.crm_admin_fields_extracted,
        dc.contact_id,
        c.company_id,
        c.company_name,
        c.email as primary_contact_email,
        c.createdate as contact_createdate,
        cc.channel as first_touch_channel,
        cc.utm_source as first_touch_utm_source,
        cc.utm_quality,
        row_number() over (
            partition by d.deal_id
            order by c.createdate nulls last, dc.contact_id
        ) as contact_rank
    from {{ ref('dim_deal') }} d
    left join {{ ref('bridge_deal_contact') }} dc on d.deal_id = dc.deal_id
    left join {{ ref('dim_contact') }} c on dc.contact_id = c.contact_id
    left join {{ ref('int_contact_channel') }} cc on dc.contact_id = cc.contact_id
),

deal_identity as (
    select *
    from deal_contact_candidates
    where contact_rank = 1 or contact_rank is null
),

company_history as (
    select
        *,
        min(deal_closedate) filter (where hs_is_closed_won) over (
            partition by company_id
        ) as first_known_company_win_date
    from deal_identity
),

reviewed_motion_overrides as (
    select * from {{ ref('gtm_deal_motion_overrides') }}
)

select
    d.deal_id,
    d.amount,
    d.dealstage,
    d.pipeline,
    d.hs_is_closed_won,
    d.deal_createdate,
    d.deal_closedate,
    d.hubspot_deal_source,
    d.hubspot_original_traffic_source,
    d.deal_owner_id,
    d.next_step,
    d.next_step_updated_at,
    d.product_service,
    d.billing_model,
    d.crm_admin_fields_extracted,
    d.contact_id,
    d.primary_contact_email,
    d.company_id,
    d.company_name,
    d.first_touch_channel,
    d.first_touch_utm_source,
    d.utm_quality,
    d.first_known_company_win_date,

    case
        when d.company_id is null then 'unmapped_company'
        when d.hs_is_closed_won and d.deal_closedate = d.first_known_company_win_date
            then 'first_known_company_win'
        when d.hs_is_closed_won then 'repeat_company_win'
        else 'not_closed_won'
    end as company_history_lifecycle,

    coalesce(o.customer_motion::text, 'unclassified') as customer_motion,
    case
        when o.customer_motion is not null then 'reviewed_override'
        when d.company_id is null then 'needs_company_association'
        else 'needs_product_or_service_lineage'
    end as customer_motion_evidence_status,
    o.evidence_note::text as customer_motion_evidence_note,
    o.reviewed_by::text as reviewed_by,
    o.reviewed_at::text as reviewed_at,

    case
        when d.first_touch_channel is null then 'missing'
        when d.utm_quality = 'clean' then 'first_touch_utm'
        when d.utm_quality = 'corrupted' then 'corrupted_utm'
        else 'inferred_or_missing_utm'
    end as attribution_evidence_status,

    current_timestamp as modeled_at
from company_history d
left join reviewed_motion_overrides o on d.deal_id = o.deal_id::text
