# Hermes shared handoff protocol

1. **Hermes CRM Admin proposes.** It uses curated read-only evidence and returns
   a complete draft. It neither persists the draft nor executes it.
2. **Codex coordinator validates.** Codex checks the target population, evidence,
   risk, rollback, and approval gate; for marketing attribution or ROI impacts it
   validates the claim against Hermes Attribution. Codex then records the reviewed
   artifact/status in `ledger/proposals.json` through repository change control.
3. **User explicitly approves.** Approval must name the exact proposal and target
   population. `approved_automation_candidate` is only a workstream label and is
   not approval by itself.
4. **Chrome MCP executes only after approval.** Execution is outside both Hermes
   services. The coordinator must reconfirm scope and preserve a rollback record.
5. **Codex logs results.** It records executor, timestamp, outcome, affected IDs or
   immutable target artifact, validation evidence, and rollback status in the ledger.

## Append-only lifecycle feed

For every future proposal creation, approval, execution start, item outcome,
reconciliation, failure, or rollback, the Codex coordinator calls
hermes_shared.execution_events.append_execution_event. Each call appends one
validated line to ledger/execution_events.jsonl. Existing lines are never edited
or removed. proposals.json remains the current-state proposal/outcome ledger;
the JSONL feed is its chronological audit companion.

The writer is coordinator-only and is not exposed as an MCP tool. Messages must
be single-line, human-readable, and free of credentials or secrets. An event is
an audit record, not CRM execution authority.

Hermes Attribution remains the authority for attribution defensibility. Hermes CRM
Admin remains the authority for proposal completeness. Neither service can execute.
