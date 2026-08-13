-- stg_brand_inbound_twitter_crosscheck — staging view over the Twitter/X cross-check.
--
-- One row per CSV Twitter/X deal (29). CROSSCHECKED rows carry PDF-observed
-- current source; NOT_CROSSCHECKED rows are neither clean nor corrupted — their
-- current source was simply never observed.
--
-- observed_mechanism is a HubSpot drill-down label, not a cause. Nothing here
-- attributes an overwrite to Zapier or to any named system.

select
    crosscheck_id,
    deal_id,
    csv_deal_name,
    csv_organisation_name,
    csv_source_value                    as historical_source,
    crosscheck_status,
    pdf_deal_name,
    pdf_current_source,
    overwrite_status,
    observed_mechanism,
    observed_creation_source,
    closed_won_flag,
    name_match_exact,
    evidence_date,
    evidence_limitations,
    csv_source_sha256,
    pdf_source_sha256,
    imported_at,
    authorizes_crm_change
from {{ source('raw', 'brand_inbound_twitter_crosscheck') }}
