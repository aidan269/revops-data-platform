import csv
import hashlib
import json
import unittest
from decimal import Decimal
from pathlib import Path

from hermes_crm_admin.codex_mcp import _review_proposal


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "hermes_shared" / "ledger" / "proposals.json"
TARGETS = ROOT / "hermes_shared" / "artifacts" / "CRM-002_deterministic_company_association_candidates.csv"
EXPECTED_HASH = "9607eb6473e6e25e02d7bcf3ac5d2290f4a83240588025b9bf3253585c5ad3cc"


class CRM002LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.proposals = {item["proposal_id"]: item for item in cls.ledger["proposals"]}
        with TARGETS.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_crm001_completed_action_is_exact_and_scoped(self):
        outcome = self.proposals["CRM-001"]["outcomes"][0]
        self.assertEqual(outcome["action"]["deal_id"], "63272092727")
        self.assertEqual(outcome["action"]["company_id"], "57215067670")
        self.assertEqual(outcome["action"]["association_label"], "Primary")
        self.assertTrue(outcome["result"]["successful"])
        self.assertFalse(outcome["result"]["other_crm_fields_or_records_changed"])

    def test_crm002_target_artifact_is_immutable_and_reconciled(self):
        digest = hashlib.sha256(TARGETS.read_bytes()).hexdigest()
        self.assertEqual(digest, EXPECTED_HASH)
        self.assertEqual(len(self.rows), 4)
        self.assertEqual(len({row["deal_id"] for row in self.rows}), 4)
        self.assertEqual(sum(Decimal(row["crm_deal_amount"]) for row in self.rows), Decimal("163673.00"))

    def test_crm002_requires_two_deterministic_identity_signals(self):
        for row in self.rows:
            self.assertEqual(row["contact_associated_company_id"], row["proposed_company_id"])
            self.assertEqual(row["email_domain"], row["company_domain"])
            self.assertEqual(row["exact_domain_company_count"], "1")
            self.assertEqual(row["current_direct_company_count"], "0")
            self.assertEqual(row["execution_authorized"], "false")

    def test_crm002_records_explicit_approval_and_execution(self):
        proposal = self.proposals["CRM-002"]
        review = _review_proposal(proposal)
        self.assertEqual(review["decision"], "ready_for_explicit_approval")
        self.assertFalse(review["execution_authorized"])
        self.assertTrue(proposal["execution_authorized"])
        self.assertEqual(proposal["status"], "executed")
        self.assertEqual(proposal["approval"]["approved_by"], "User via Terminal Codex")
        self.assertEqual(len(proposal["outcomes"]), 4)
        self.assertTrue(all(item["status"] == "successful" for item in proposal["outcomes"]))
        self.assertTrue(all(item["verification"] == "Companies changed from 0 to 1." for item in proposal["outcomes"]))
        self.assertFalse(proposal["execution_result"]["other_crm_fields_or_records_changed"])

    def test_unsupported_p1_records_are_excluded(self):
        proposal = self.proposals["CRM-002"]
        excluded = set(proposal["evidence"]["exclusions"]["remaining_p1_missing_company_deals"])
        target_ids = {row["deal_id"] for row in self.rows}
        self.assertEqual(excluded, {"52040513372", "59186399278", "60254137863"})
        self.assertTrue(excluded.isdisjoint(target_ids))


if __name__ == "__main__":
    unittest.main()
