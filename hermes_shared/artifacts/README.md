# Evidence artifacts (not committed)

Generated evidence — inventories, manifests, findings, simulation results — is
written here at runtime and is **deliberately excluded from Git**.

Why: these outputs describe live CRM state and can contain record identifiers.
They are operational evidence, not source code, and they change on every run.

Regenerate them from configured sources:

```
export DATABASE_URL=postgresql://<user>:<pass>@localhost:5432/warehouse
python -m automation_twin.cli import-evidence
python scripts/load_automation_twin.py --database-url "$DATABASE_URL"
```

Override locations with `REVOPS_ARTIFACT_ROOT` and `REVOPS_LEDGER_PATH`.
The audit ledger (`hermes_shared/ledger/*.jsonl`) is likewise untracked.
