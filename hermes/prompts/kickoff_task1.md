# Kickoff — Task 1: stand up the platform and land first data

Follow the guardrails in `system.md`. Deterministic only. **Do not write to HubSpot** in
this task. Report results with table names + row counts at each step.

1. **Bring up the stack.** `docker compose up -d`. Confirm Postgres (5432), Adminer
   (http://localhost:8080), and the ingest service (http://localhost:8000) are healthy.
2. **Point ingestion at Postgres.** Take the landing-zone prototype (`ingest.py`) and make
   it write to `raw.leads_raw` via `DATABASE_URL` instead of the local JSONL file. Keep it
   append-only and keep `record_hash`.
3. **Prove capture.** POST two payloads to `/ingest`: one clean
   (`utm_source=google&utm_medium=cpc&email=a@b.com`) and one corrupted
   (`utm_source=utm_medium:&utm_medium=utm_campaign:&email=bad@x.com`). Confirm both land
   intact in `raw.leads_raw`.
4. **Scaffold dbt.** Init the dbt project in `transform/` with a Postgres profile. Build
   `stg_leads` from `raw.leads_raw`. Add the tests: `not_null` + `unique` on `event_id`,
   and `accepted_values` on `utm_source` (wire the accepted list from the real values in
   `../landing-zone/dbt/models/staging/schema.yml`).
5. **Run it.** `dbt build`. Confirm the `accepted_values` test **flags the corrupted row**
   (`utm_source = "utm_medium:"`) while the clean row passes.

Success = raw capture working against Postgres + dbt staging built + the UTM alarm firing on
the corrupted record. Then stop and report; Task 2 will be the marts + the guarded writeback.
