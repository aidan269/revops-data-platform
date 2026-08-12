-- mart_gtm_campaign_performance_live — one row per GTM Campaign.
--
-- Measures campaigns by the contacts, deals, pipeline and closed-won outcomes
-- they are DIRECTLY ASSOCIATED WITH in HubSpot. Every metric below is an
-- observed association, not an attribution claim.
--
-- Deliberate boundaries:
--   * Deal counts and amounts come only from campaign→deal association edges.
--     A deal is never pulled into a campaign because an associated contact
--     happens to be a member, nor from UTM, email clicks, or web clicks.
--   * "influenced_*" names the associated-deal measures honestly. Nothing in
--     this model supports a "sourced" claim; sourcing requires first-touch
--     evidence this warehouse does not yet hold.
--   * Amounts are HubSpot CRM deal amount. They are NOT ARR and NOT recognized
--     revenue. Column names carry that boundary so a reader cannot lose it.

with campaigns as (
    select * from {{ ref('stg_gtm_campaigns') }}
),

contact_links as (
    select gtm_campaign_id, count(distinct contact_id) as associated_contacts
    from {{ ref('stg_gtm_campaign_contacts') }}
    group by 1
),

-- Contacts that resolve to a real contact record in the live warehouse.
contact_quality as (
    select
        l.gtm_campaign_id,
        count(distinct l.contact_id) filter (where c.contact_id is not null)
            as resolvable_contacts
    from {{ ref('stg_gtm_campaign_contacts') }} l
    left join {{ ref('dim_contact') }} c on c.contact_id = l.contact_id
    group by 1
),

deals as (
    select
        l.gtm_campaign_id,
        l.deal_id,
        d.deal_id as resolved_deal_id,
        d.amount,
        d.hs_is_closed_won,
        d.dealstage,
        d.billing_model,
        d.deal_closedate
    from {{ ref('stg_gtm_campaign_deals') }} l
    left join {{ ref('mart_gtm_lifecycle_live') }} d on d.deal_id = l.deal_id
),

deal_metrics as (
    select
        gtm_campaign_id,
        count(distinct deal_id)                                   as associated_deals,
        count(distinct resolved_deal_id)                          as resolvable_deals,

        -- CRM deal amount. NOT ARR. NOT recognized revenue.
        coalesce(sum(amount), 0)                                  as influenced_crm_deal_amount,
        count(*) filter (where amount is null)                    as deals_missing_amount,

        -- Open pipeline: associated deals that are neither won nor lost.
        count(distinct resolved_deal_id) filter (
            where hs_is_closed_won = false and dealstage is distinct from 'closedlost'
        )                                                          as open_deals,
        coalesce(sum(amount) filter (
            where hs_is_closed_won = false and dealstage is distinct from 'closedlost'
        ), 0)                                                      as open_pipeline_crm_deal_amount,

        count(distinct resolved_deal_id) filter (where hs_is_closed_won)
                                                                   as closed_won_deals,
        coalesce(sum(amount) filter (where hs_is_closed_won), 0)
                                                                   as closed_won_crm_deal_amount,

        count(distinct resolved_deal_id) filter (where dealstage = 'closedlost')
                                                                   as closed_lost_deals,

        -- Closed ARR per Viv's definition, carried through for cross-reference.
        count(distinct resolved_deal_id) filter (
            where hs_is_closed_won and billing_model = 'Subscription - ARR'
        )                                                          as closed_arr_deals
    from deals
    group by 1
)

select
    c.gtm_campaign_id,
    coalesce(c.campaign_name, '(unnamed campaign)')       as campaign_name,
    c.archived,
    c.created_at                                          as campaign_created_at,

    coalesce(cl.associated_contacts, 0)                   as associated_contacts,
    coalesce(cq.resolvable_contacts, 0)                   as resolvable_contacts,
    coalesce(cl.associated_contacts, 0)
        - coalesce(cq.resolvable_contacts, 0)             as unresolvable_contacts,

    coalesce(dm.associated_deals, 0)                      as associated_deals,
    coalesce(dm.resolvable_deals, 0)                      as resolvable_deals,
    coalesce(dm.associated_deals, 0)
        - coalesce(dm.resolvable_deals, 0)                as unresolvable_deals,

    coalesce(dm.influenced_crm_deal_amount, 0)            as influenced_crm_deal_amount,
    coalesce(dm.deals_missing_amount, 0)                  as deals_missing_amount,
    coalesce(dm.open_deals, 0)                            as open_deals,
    coalesce(dm.open_pipeline_crm_deal_amount, 0)         as open_pipeline_crm_deal_amount,
    coalesce(dm.closed_won_deals, 0)                      as closed_won_deals,
    coalesce(dm.closed_won_crm_deal_amount, 0)            as closed_won_crm_deal_amount,
    coalesce(dm.closed_lost_deals, 0)                     as closed_lost_deals,
    coalesce(dm.closed_arr_deals, 0)                      as closed_arr_deals,

    -- Association-quality gaps. These drive the "what evidence is missing"
    -- answer and must never be silently dropped from reporting.
    case when coalesce(cl.associated_contacts, 0) = 0 then true else false end
        as gap_no_associated_contacts,
    case when coalesce(dm.associated_deals, 0) = 0 then true else false end
        as gap_no_associated_deals,
    case when c.campaign_name is null then true else false end
        as gap_missing_campaign_name,
    case when coalesce(dm.associated_deals, 0)
              > coalesce(dm.resolvable_deals, 0) then true else false end
        as gap_deal_not_in_live_warehouse,
    case when coalesce(dm.deals_missing_amount, 0) > 0 then true else false end
        as gap_deal_missing_amount,

    -- A campaign is measurable only when it has at least one resolvable deal.
    case when coalesce(dm.resolvable_deals, 0) > 0
         then 'measurable_influence'
         else 'not_yet_measurable' end                    as measurement_status,

    'crm_deal_amount_not_arr_not_recognized_revenue'      as amount_basis,
    'associated_influence_only_not_sourced'               as attribution_basis,
    current_timestamp                                     as modeled_at
from campaigns c
left join contact_links cl on cl.gtm_campaign_id = c.gtm_campaign_id
left join contact_quality cq on cq.gtm_campaign_id = c.gtm_campaign_id
left join deal_metrics dm on dm.gtm_campaign_id = c.gtm_campaign_id
order by closed_won_crm_deal_amount desc, open_pipeline_crm_deal_amount desc, campaign_name
