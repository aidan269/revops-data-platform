import tempfile
import unittest
from pathlib import Path

from hermes_crm_admin.codex_mcp import (
    _draft_proposal,
    _load_ledger,
    _open_proposals,
    _proposal_issues,
    _review_proposal,
    _weekly_report,
)


def valid_proposal(**overrides):
    proposal = {
        "proposal_id": "CRM-001", "title": "Review missing association",
        "change_type": "association", "workstream": "manual_review", "status": "proposed",
        "target_population": {"selection_rule": "curated queue row", "record_count": 1, "record_ids_or_artifact": "artifacts/CRM-001-targets.csv#sha256:example"},
        "evidence": {"source_models": ["mart_deal_cleanup_queue_live"], "rationale": "Direct association is absent."},
        "expected_change": {"object_or_configuration": "deal", "field_or_setting": "company association", "proposed_value": "reviewed company ID"},
        "risk": "Wrong-company association", "rollback_approach": "Remove the approved association and restore the logged prior state.",
        "approval": {"required": True, "approver_role": "Sales Ops", "approved_by": None},
    }
    proposal.update(overrides)
    return proposal


class CRMAdminSafetyTests(unittest.TestCase):
    def test_refuses_crm_write_authority(self):
        review = _review_proposal(valid_proposal())
        self.assertFalse(review["execution_authorized"])
        self.assertIn("never executes CRM writes", review["control_plane_boundary"])

    def test_refuses_browser_click_instructions(self):
        proposal = valid_proposal(rollback_approach="Open HubSpot and click Save")
        self.assertIn("prohibited_execution_or_browser_instruction", _proposal_issues(proposal))
        self.assertEqual(_review_proposal(proposal)["decision"], "blocked")

    def test_refuses_unsupported_enrichment(self):
        proposal = valid_proposal(change_type="enrichment")
        self.assertIn("unsupported_enrichment_requires_authoritative_source", _proposal_issues(proposal))

    def test_refuses_unapproved_bulk_action(self):
        proposal = valid_proposal(
            target_population={"selection_rule": "all contacts", "record_count": 10000, "record_ids_or_artifact": "artifacts/bulk.csv#sha256:example"},
            approval={"required": False, "approver_role": "RevOps"},
        )
        review = _review_proposal(proposal)
        self.assertEqual(review["decision"], "blocked")
        self.assertFalse(review["execution_authorized"])

    def test_draft_is_not_persisted_or_authorized(self):
        result = _draft_proposal(
            "CRM-002", "Proposal", "crm_hygiene", "manual_review", "queue = true", 2, "IDs: 1,2",
            "mart_deal_cleanup_queue_live", "Missing field", "deal", "deal source",
            "reviewed value", "Misclassification", "Restore logged old value", "RevOps",
        )
        self.assertFalse(result["persisted"])
        self.assertFalse(result["review"]["execution_authorized"])

    def test_ledger_separates_workstreams_and_weekly_report(self):
        ledger = {"schema_version": "1.0.0", "proposals": [
            valid_proposal(), valid_proposal(proposal_id="CRM-002", workstream="approved_automation_candidate")
        ]}
        self.assertEqual(len(_open_proposals(ledger)), 2)
        report = _weekly_report({"live_deals": 10}, ledger)
        self.assertEqual(report["proposal_ledger"]["open_automation_candidates"], 1)
        self.assertEqual(report["proposal_ledger"]["open_manual_review"], 1)


if __name__ == "__main__":
    unittest.main()
