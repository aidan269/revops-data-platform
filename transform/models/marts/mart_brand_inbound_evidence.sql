-- mart_brand_inbound_evidence — read-only comparison of historical brand inbound
-- evidence against the latest HubSpot deal snapshot, joined on exact deal ID.
--
-- CONTRACT: historical evidence never supersedes the live snapshot.
--   * live_* columns are the current warehouse snapshot and are authoritative.
--   * historical_* and pdf_* columns are human-maintained evidence about the past.
--   * agreement_status describes the RELATIONSHIP between them. It is a
--     comparison result, never an instruction to change a CRM record.
--   * Every row carries authorizes_crm_change = false.
--
-- A deal absent from the live snapshot yields live_snapshot_present = false
-- rather than being dropped, so missing coverage stays visible instead of
-- silently reducing the row count.

with crosscheck as (
    select * from {{ ref('stg_brand_inbound_twitter_crosscheck') }}
),

live as (
    select
        deal_id,
        extracted_at        as live_extracted_at,
        dealstage           as live_dealstage,
        pipeline            as live_pipeline,
        deal_source         as live_deal_source,
        original_traffic_source as live_original_traffic_source,
        hs_is_closed_won    as live_is_closed_won
    from {{ ref('stg_hubspot_deals') }}
),

joined as (
    select
        c.deal_id,
        c.csv_deal_name,
        c.csv_organisation_name,
        c.historical_source,
        c.crosscheck_status,
        c.pdf_deal_name,
        c.pdf_current_source,
        c.overwrite_status,
        c.observed_mechanism,
        c.observed_creation_source,
        c.closed_won_flag        as pdf_closed_won_flag,
        c.name_match_exact,
        c.evidence_date          as pdf_evidence_date,
        c.evidence_limitations,
        l.deal_id is not null    as live_snapshot_present,
        l.live_extracted_at,
        l.live_dealstage,
        l.live_pipeline,
        l.live_deal_source,
        l.live_original_traffic_source,
        l.live_is_closed_won
    from crosscheck c
    left join live l on l.deal_id = c.deal_id
)

select
    *,
    case
        when not live_snapshot_present
            then 'NO_LIVE_SNAPSHOT'
        when crosscheck_status = 'NOT_CROSSCHECKED'
            then 'HISTORICAL_ONLY_NOT_CROSSCHECKED'
        when live_original_traffic_source is null
            then 'LIVE_SOURCE_NULL'
        when lower(live_original_traffic_source) = lower(pdf_current_source)
            then 'LIVE_MATCHES_PDF_OBSERVATION'
        else 'LIVE_DIFFERS_FROM_PDF_OBSERVATION'
    end as agreement_status,
    'historical evidence; compare only. never supersedes the live snapshot' as usage_contract,
    false as authorizes_crm_change
from joined
