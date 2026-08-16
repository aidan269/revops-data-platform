# RevOps Data Platform

HubSpot is where people *work*; this warehouse is where *history lives*.
Ingestion → raw → transform (dbt) → curated → serve, with controlled write-back to HubSpot.
The Hermes agent reads the curated layer and runs deterministic jobs.

- **Full design:** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Agent prompts (version-controlled):** [hermes/prompts/](hermes/prompts/)
- **Quickstart:** `docker compose up -d`

Kickoff tasks for Hermes live in `hermes/prompts/kickoff_task*.md`.

## Automation digital twin

A vendor-neutral model of the automation estate — HubSpot, Apollo, Zapier, forms,
the warehouse and the audit ledger — built into one graph you can query and
simulate against. It exists to answer three questions safely: what automation do
we have, what can it write, and what would happen if it ran?

**Dry-run guarantee.** The simulator proposes writes; it cannot perform them.
No module imports a write-capable external client (a test greps for them), the
LangGraph approval interrupt is followed by a terminal `safe_stop` node with
nothing after it, and the CLI has no `execute` command. A test proves that an
*approved* simulated state still cannot mutate HubSpot, Apollo or Zapier.

**Approval boundary.** Any external mutation would require a row in
`raw.automation_approvals`, which is the only table permitted to set
`authorizes_external_write = true`, and only with a named approver and timestamp.
Every other evidence table pins that column to false by CHECK constraint.

**Collected vs unresolved.** The graph records what it cannot see. Surfaces that
were never collected are `NOT_COLLECTED` with a reason and can never claim a
baseline — enforced in the dataclass, by a database CHECK, and by a dbt test.
Assets known to exist but whose definitions were never collected appear as stubs
with **no invented nodes or edges**.

### Running it

```bash
export DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/warehouse
python scripts/run_db_migrations.py --database-url "$DATABASE_URL"   # migrations
pytest tests/ -q                                                     # tests
python -m automation_twin.cli validate-graph                         # graph integrity
python scripts/load_automation_twin.py                               # load graph into Postgres
python -m automation_twin.cli simulate valid_campaign_propagation    # dry-run
python -m automation_twin.cli baseline-coverage                      # coverage
python -m automation_twin.cli unresolved                             # what we cannot see
cd transform && dbt build --profiles-dir . --target warehouse        # models
```

`load_automation_twin.py` is refresh-safe: re-running updates entities in place
and records a new load, so a corrected observation is never frozen behind its
first write. Current-state marts select the latest load; history is retained.

Runtime locations are configurable and default to repository-relative paths:
`REVOPS_ARTIFACT_ROOT`, `REVOPS_LEDGER_PATH`, `REVOPS_CHECKPOINT_PATH`,
`DATABASE_URL`.
