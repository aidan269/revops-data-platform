# RevOps Data Platform

HubSpot is where people *work*; this warehouse is where *history lives*.
Ingestion → raw → transform (dbt) → curated → serve, with controlled write-back to HubSpot.
The Hermes agent reads the curated layer and runs deterministic jobs.

- **Full design:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Agent prompts (version-controlled):** [hermes/prompts/](hermes/prompts/)
- **Quickstart:** `docker compose up -d`

Kickoff tasks for Hermes live in `hermes/prompts/kickoff_task*.md`.
