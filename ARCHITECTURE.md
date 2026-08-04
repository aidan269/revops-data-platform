# RevOps Data Platform — Architecture

**Principle:** HubSpot is where people *work*; it is not where *history lives*. The data
layer below owns ingestion, raw storage, transforms, and curated tables. Analytics and
the Hermes agent read from the curated layer. Writes back into HubSpot are few,
deterministic, and guarded.

## The layers

```
        +------------------- HubSpot (system of WORK) -------------------+
        |   forms · deals · contacts · workflows (people work here)      |
        +---------+-------------------------------------------+---------+
                  | (1) capture                                ^ (5) controlled write-back
                  v                                            |
  +------- INGESTION -------+   +---- TRANSFORM (dbt) ----+   +--- SERVE ----+
  | webhook + Fivetran/     |-->| raw -> staging ->       |-->| curated      |
  | Airbyte -> raw (append) |   | intermediate -> marts   |   | tables/views |
  +-------------------------+   +-------------------------+   +------+-------+
                  |                                                  |
                  v                                                  v
             RAW (immutable)                          ANALYTICS + HERMES read here
```

- **Capture / Ingestion** — every inbound payload lands append-only and untouched (the
  landing zone). Plus scheduled extracts of HubSpot objects (contacts, deals, engagements).
- **Raw** — immutable "bronze." Never edited. This is what makes corruption replayable.
- **Transform (dbt)** — `staging → intermediate → marts`. All business logic (scoring,
  attribution, cycle time) lives here as version-controlled SQL = single source of truth.
- **Curated / Serve** — clean marts + views. Dashboards and Hermes read only from here.
- **Controlled write-back** — a small, guarded reverse-ETL that pushes a *whitelist* of
  curated fields (e.g. lead grade, ICP score) back into HubSpot. Everything else is read-only.

## Stack (free/local now → production later)

| Layer | Free / local (this build) | Production upgrade |
|---|---|---|
| Warehouse | **Postgres** (Docker) | Snowflake / BigQuery |
| Ingestion | FastAPI webhook + Python extracts | Fivetran / Airbyte |
| Transform | **dbt-postgres** | dbt + Snowflake |
| Orchestration | cron / a Python runner | **Dagster** or **Prefect** |
| Reverse-ETL | small Python writer (whitelist) | Hightouch / Census |
| LLM backend | **Ollama** + local model (e.g. Llama 3.1 8B) | hosted API when needed |

Runs on the second Mac as a Docker-based "AI backend server." Your main laptop stays on
Slack/Notion and stays responsive.

## Controlled write-back (the safety rule)

- Hermes and analytics **read** from curated tables.
- Writes to HubSpot go through **one** module (`writeback/`) with an explicit field
  whitelist, dry-run by default, and a log of every change.
- Never write to `raw`. Never let the agent free-write arbitrary HubSpot fields.

## Hermes's role

Hermes is a RevOps/Marketing-Ops agent that reads curated data and runs **deterministic**
jobs (SQL/dbt/Python), not creative changes. It proposes HubSpot writes; the whitelist +
dry-run enforce safety. Prompts live in `hermes/prompts/` as version-controlled files.

## Cost

- Local build: effectively **$0** (Postgres + dbt + Ollama + Python, all open/local).
- Production-like for a small team: typically **< a couple hundred / month** (managed
  warehouse + ELT + reverse-ETL seats).

## Career skills this builds

SQL, Python, webhooks, ELT/ETL patterns, dbt modeling + testing, Docker, and (as it grows)
Dagster/Prefect orchestration. A modern data-engineer stack — a much stronger story than
"managed 20 Zaps."

## Repo layout

```
revops-data-platform/
  ARCHITECTURE.md
  docker-compose.yml       # postgres + ollama + adminer + ingest (second-Mac backend)
  db/init.sql              # Postgres raw + analytics schemas
  ingestion/               # webhook landing zone (see ../landing-zone prototype)
  transform/               # dbt project (staging -> marts)
  writeback/               # guarded HubSpot writer (whitelist, dry-run)
  hermes/prompts/          # version-controlled agent prompts
```

## Run it

```bash
docker compose up -d        # postgres + ollama + adminer + ingest
ollama pull llama3.1        # first run: pull the local model
# point HubSpot forms / Make at http://<second-mac-ip>:8000/ingest
```

## Decisions you can flip

- **Warehouse:** Postgres (chosen — prod-like, resume-friendly, runs in Docker). Swap for
  DuckDB if you want an even lighter, file-based local build.
- **Orchestration:** start with cron/a Python runner; add **Dagster** or **Prefect** once
  there's more than one scheduled job — that's the resume-grade upgrade.
- **Local model:** Llama 3.1 8B is a fine default via Ollama; size up if enrichment
  classification needs it.
