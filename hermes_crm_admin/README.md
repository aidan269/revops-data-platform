# Hermes CRM Admin

This is a separate, guarded MCP service from Hermes Attribution. Configure it as
`hermes_crm_admin` in Terminal Codex and pass the same read-only `DATABASE_URL`.

```toml
[mcp_servers.hermes_crm_admin]
command = "/absolute/path/to/repository/.venv/bin/python"
args = ["/absolute/path/to/repository/hermes_crm_admin/codex_mcp.py"]

[mcp_servers.hermes_crm_admin.env]
DATABASE_URL = "postgresql://hermes_reader:REPLACE@127.0.0.1:5432/warehouse"
```

Tools:

- `hermes_crm_admin_health_summary`
- `hermes_crm_admin_draft_proposal`
- `hermes_crm_admin_proposed_change_review`
- `hermes_crm_admin_open_proposals`
- `hermes_crm_admin_weekly_report`

The draft tool returns an unpersisted proposal and never authorizes execution.
The other tools read only fixed marts or the repository ledger. See the
versioned playbook and `hermes_shared/HANDOFF_PROTOCOL.md`.

Run safety evals from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s hermes/tests -v
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s hermes_crm_admin/tests -v
```
