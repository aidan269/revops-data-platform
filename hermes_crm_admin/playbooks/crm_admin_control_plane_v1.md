# Hermes CRM Admin control-plane playbook

Version: 1.0.0

Hermes CRM Admin is a separate, proposal-only MCP service. It reads fixed curated
warehouse marts and the shared proposal ledger. It cannot execute HubSpot or
database writes, browser actions, shell commands, or source-data changes.

Every proposal must specify an exact selection rule, record count, and either
explicit record IDs or a versioned target artifact with an integrity hash; curated
evidence, the exact object/configuration and proposed value, risk, rollback,
and a named approval role. Enrichment also requires an authoritative source.
Absence of evidence is a manual-review outcome, never permission to infer data.

`approved_automation_candidate` means technically deterministic and potentially
automatable after approval. It does not mean approved. `manual_review` means a
human must resolve identity, lineage, ambiguity, or business judgment.

The MCP has no ledger-write tool. The Codex coordinator validates and persists
proposal/status artifacts through repository review so changes remain visible
and auditable.

The coordinator also appends one lifecycle record to
hermes_shared/ledger/execution_events.jsonl for every future proposal and
reconciliation step using the shared append-only writer. Hermes CRM Admin never
invokes that writer itself.
