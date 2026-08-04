-- staging: one row per raw lead event, typed + lightly normalized.
-- Reads FROM the append-only landing table. Never mutates raw.
with source as (
    select * from {{ source('raw', 'leads_raw') }}
)

select
    event_id,
    received_at,
    source                                  as lead_source,
    form_id,
    lower(raw_payload:utm_source::string)   as utm_source,
    lower(raw_payload:utm_medium::string)   as utm_medium,
    raw_payload:utm_campaign::string        as utm_campaign,
    raw_payload:email::string               as email,
    record_hash,
    status
from source
