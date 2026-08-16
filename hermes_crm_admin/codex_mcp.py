#!/usr/bin/env python3
"""Read-only CRM-admin proposal and review control plane for Terminal Codex."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("hermes-crm-admin")
PLAYBOOK_VERSION = "1.0.0"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = REPOSITORY_ROOT / "hermes_shared" / "ledger" / "proposals.json"
MAX_ROWS = 500

CRM_HEALTH_SQL = """
SELECT
  (SELECT count(*) FROM analytics_analytics.mart_gtm_lifecycle_live) AS live_deals,
  (SELECT count(*) FROM analytics_analytics.mart_deal_cleanup_queue_live) AS open_deal_hygiene_reviews,
  (SELECT count(*) FROM analytics_analytics.mart_deal_cleanup_queue_live
    WHERE remediation_reasons LIKE '%missing_deal_source%') AS deals_missing_deal_source,
  (SELECT count(*) FROM analytics_analytics.mart_deal_cleanup_queue_live
    WHERE remediation_reasons LIKE '%missing_direct_company_association%') AS deals_missing_direct_company_association,
  (SELECT count(*) FROM analytics_analytics.mart_enrichment_gaps WHERE has_any_gap) AS contacts_with_enrichment_gaps,
  (SELECT count(*) FROM analytics_analytics.mart_enrichment_gaps WHERE gap_hs_seniority) AS contacts_missing_seniority,
  (SELECT count(*) FROM analytics_analytics.mart_enrichment_gaps WHERE gap_industry) AS contacts_missing_industry,
  (SELECT count(*) FROM analytics_analytics.mart_enrichment_gaps WHERE gap_hs_employee_range) AS contacts_missing_employee_range,
  (SELECT count(*) FROM analytics_analytics.mart_customer_motion_review_queue_live) AS customer_motion_manual_reviews
"""

ALLOWED_CHANGE_TYPES = {
    "crm_hygiene", "enrichment", "association", "property_configuration",
    "workflow_configuration", "deduplication",
}
ALLOWED_WORKSTREAMS = {"approved_automation_candidate", "manual_review"}
OPEN_STATUSES = {"draft", "proposed", "awaiting_approval", "approved", "partially_executed"}
PROHIBITED_TERMS = {
    "click save", "click the", "open hubspot", "log into hubspot", "use chrome",
    "browser click", "execute write", "update the crm", "bulk update now",
}


def _database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL must be a read-only Postgres connection string.")
    return value


def _json_value(value: Any) -> Any:
    return str(value) if isinstance(value, (date, datetime, Decimal)) else value


def _run_health_query() -> dict[str, Any]:
    try:
        connection = psycopg2.connect(_database_url(), connect_timeout=10)
        connection.set_session(readonly=True, autocommit=False)
        with connection, connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '15s'")
            cursor.execute(CRM_HEALTH_SQL)
            columns = [column.name for column in cursor.description]
            row = cursor.fetchone()
    except psycopg2.Error as error:
        raise RuntimeError(f"Warehouse query failed: {error.pgerror or str(error)}") from error
    finally:
        if "connection" in locals():
            connection.close()
    return {column: _json_value(value) for column, value in zip(columns, row)}


def _load_ledger(path: Path = LEDGER_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "1.0.0" or not isinstance(data.get("proposals"), list):
        raise RuntimeError("Proposal ledger is not a supported versioned ledger.")
    return data


def _contains_prohibited_instruction(value: Any) -> bool:
    text = json.dumps(value, sort_keys=True).lower()
    return any(term in text for term in PROHIBITED_TERMS)


def _proposal_issues(proposal: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required = [
        "proposal_id", "title", "change_type", "workstream", "status",
        "target_population", "evidence", "expected_change", "risk",
        "rollback_approach", "approval",
    ]
    for field in required:
        if field not in proposal or proposal[field] in (None, "", [], {}):
            issues.append(f"missing_required_field:{field}")
    if proposal.get("change_type") not in ALLOWED_CHANGE_TYPES:
        issues.append("unsupported_change_type")
    if proposal.get("workstream") not in ALLOWED_WORKSTREAMS:
        issues.append("invalid_workstream")
    target = proposal.get("target_population", {})
    if not isinstance(target, dict) or not target.get("selection_rule") or target.get("record_count") is None:
        issues.append("target_population_requires_selection_rule_and_record_count")
    if isinstance(target, dict) and not target.get("record_ids_or_artifact"):
        issues.append("target_population_requires_record_ids_or_versioned_artifact")
    evidence = proposal.get("evidence", {})
    if not isinstance(evidence, dict) or not evidence.get("source_models") or not evidence.get("rationale"):
        issues.append("evidence_requires_source_models_and_rationale")
    if proposal.get("change_type") == "enrichment" and not evidence.get("authoritative_source"):
        issues.append("unsupported_enrichment_requires_authoritative_source")
    expected = proposal.get("expected_change", {})
    if not isinstance(expected, dict) or not expected.get("object_or_configuration") or not expected.get("field_or_setting") or "proposed_value" not in expected:
        issues.append("expected_change_requires_object_field_and_value")
    approval = proposal.get("approval", {})
    if not isinstance(approval, dict) or approval.get("required") is not True or not approval.get("approver_role"):
        issues.append("explicit_approval_required")
    if proposal.get("status") == "approved" and not approval.get("approved_by"):
        issues.append("approved_status_requires_named_approver")
    if _contains_prohibited_instruction(proposal):
        issues.append("prohibited_execution_or_browser_instruction")
    return sorted(set(issues))


def _review_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    issues = _proposal_issues(proposal)
    return {
        "proposal_id": proposal.get("proposal_id"),
        "decision": "blocked" if issues else "ready_for_explicit_approval",
        "issues": issues,
        "execution_authorized": False,
        "approval_requirement": "A named user must explicitly approve the exact target population and expected change.",
        "control_plane_boundary": "Hermes CRM Admin never executes CRM writes, browser actions, shell commands, or source-data writes.",
    }


def _draft_proposal(
    proposal_id: str,
    title: str,
    change_type: str,
    workstream: str,
    selection_rule: str,
    record_count: int,
    record_ids_or_artifact: str,
    source_models_csv: str,
    evidence_rationale: str,
    object_or_configuration: str,
    field_or_setting: str,
    proposed_value: str,
    risk: str,
    rollback_approach: str,
    approver_role: str,
    authoritative_source: str = "",
) -> dict[str, Any]:
    evidence = {
        "source_models": [item.strip() for item in source_models_csv.split(",") if item.strip()],
        "rationale": evidence_rationale,
    }
    if authoritative_source:
        evidence["authoritative_source"] = authoritative_source
    proposal = {
        "proposal_id": proposal_id,
        "title": title,
        "change_type": change_type,
        "workstream": workstream,
        "status": "draft",
        "target_population": {
            "selection_rule": selection_rule,
            "record_count": record_count,
            "record_ids_or_artifact": record_ids_or_artifact,
        },
        "evidence": evidence,
        "expected_change": {
            "object_or_configuration": object_or_configuration,
            "field_or_setting": field_or_setting,
            "proposed_value": proposed_value,
        },
        "risk": risk,
        "rollback_approach": rollback_approach,
        "approval": {"required": True, "approver_role": approver_role, "approved_by": None, "approved_at": None},
        "created_by": "hermes_crm_admin",
        "playbook_version": PLAYBOOK_VERSION,
    }
    return {"proposal": proposal, "review": _review_proposal(proposal), "persisted": False}


def _open_proposals(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [proposal for proposal in ledger["proposals"] if proposal.get("status") in OPEN_STATUSES]


def _weekly_report(health: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    open_items = _open_proposals(ledger)
    statuses = Counter(str(item.get("status", "unknown")) for item in ledger["proposals"])
    workstreams = Counter(str(item.get("workstream", "unknown")) for item in open_items)
    return {
        "playbook_version": PLAYBOOK_VERSION,
        "crm_health": health,
        "proposal_ledger": {
            "total": len(ledger["proposals"]),
            "open": len(open_items),
            "by_status": dict(sorted(statuses.items())),
            "open_automation_candidates": workstreams.get("approved_automation_candidate", 0),
            "open_manual_review": workstreams.get("manual_review", 0),
        },
        "approval_boundary": "No proposal is execution authority. Chrome MCP may act only after explicit user approval validated by the Codex coordinator.",
        "source_models": [
            "analytics_analytics.mart_gtm_lifecycle_live",
            "analytics_analytics.mart_deal_cleanup_queue_live",
            "analytics_analytics.mart_enrichment_gaps",
            "analytics_analytics.mart_customer_motion_review_queue_live",
        ],
    }


@mcp.tool()
def hermes_crm_admin_health_summary() -> dict[str, Any]:
    """Return deterministic CRM-health counts from fixed curated read-only marts."""
    return {"playbook_version": PLAYBOOK_VERSION, "metrics": _run_health_query()}


@mcp.tool()
def hermes_crm_admin_draft_proposal(
    proposal_id: str, title: str, change_type: str, workstream: str,
    selection_rule: str, record_count: int, record_ids_or_artifact: str, source_models_csv: str,
    evidence_rationale: str, object_or_configuration: str, field_or_setting: str,
    proposed_value: str, risk: str, rollback_approach: str, approver_role: str,
    authoritative_source: str = "",
) -> dict[str, Any]:
    """Generate, but never persist or execute, a guarded CRM-change proposal."""
    return _draft_proposal(
        proposal_id, title, change_type, workstream, selection_rule, record_count, record_ids_or_artifact,
        source_models_csv, evidence_rationale, object_or_configuration,
        field_or_setting, proposed_value, risk, rollback_approach, approver_role,
        authoritative_source,
    )


@mcp.tool()
def hermes_crm_admin_proposed_change_review(proposal_id: str) -> dict[str, Any]:
    """Review one ledger proposal for evidence, completeness, and approval gates."""
    ledger = _load_ledger()
    proposal = next((item for item in ledger["proposals"] if item.get("proposal_id") == proposal_id), None)
    if proposal is None:
        return {"proposal_id": proposal_id, "decision": "not_found", "execution_authorized": False}
    return {"proposal": proposal, "review": _review_proposal(proposal)}


@mcp.tool()
def hermes_crm_admin_open_proposals() -> dict[str, Any]:
    """List open proposals, separated into automation candidates and manual review."""
    proposals = _open_proposals(_load_ledger())
    return {
        "approved_automation_candidates": [p for p in proposals if p.get("workstream") == "approved_automation_candidate"],
        "manual_review": [p for p in proposals if p.get("workstream") == "manual_review"],
        "execution_authorized": False,
    }


@mcp.tool()
def hermes_crm_admin_weekly_report() -> dict[str, Any]:
    """Return weekly CRM health and proposal governance status without writes."""
    return _weekly_report(_run_health_query(), _load_ledger())


if __name__ == "__main__":
    mcp.run()
