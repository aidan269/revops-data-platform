# Lead Landing Zone (v1)

The raw ingestion layer the 138 corrupted-UTM records proved we were missing.

## The idea
**Capture raw first, map second, test always.** Every inbound form/lead payload
lands append-only and untouched *before* any field mapping. Downstream mapping
reads *from* the landing table; if a mapping bug ships, you replay from raw
instead of losing the data forever.

## Pieces
- **`schema.sql`** — the `raw.leads_raw` landing table (Snowflake) + idempotent upsert.
- **`ingest.py`** — a FastAPI endpoint. Point every HubSpot form / Make webhook at
  `POST /ingest`; it writes the full raw payload + a `record_hash`. Runs locally
  against a JSONL file so you can try it with zero infra.
- **`dbt/`** — `stg_leads` reads from raw; `schema.yml` carries the tests:
  `not_null` + `unique` on `event_id`, freshness on the feed, and an
  `accepted_values` check on `utm_source`.

## Why this stops the next 138
The corruption was `utm_source = "utm_medium:"` — every value shifted one field over.
1. With raw capture, the original querystring is preserved → it's **replayable**.
2. The `accepted_values` test fails the moment `"utm_medium:"` appears → an
   **alarm on day one**, not 15 months later.

## v1 scope (a weekend)
Landing table + ingest endpoint + the one `accepted_values` test. Then:
Fivetran/Airbyte HubSpot → Snowflake, dbt marts, reverse-ETL — see the
data-engineering backbone section in the GTM laundry-list project.

## Try it
```bash
pip install fastapi uvicorn python-multipart
uvicorn ingest:app --reload
# in another shell:
curl -X POST localhost:8000/ingest -d 'utm_source=google&utm_medium=cpc&email=a@b.com'
cat leads_raw.jsonl
```
