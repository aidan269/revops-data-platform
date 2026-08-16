import csv
import hashlib
import json
import re
import unittest
from decimal import Decimal
from pathlib import Path

from hermes_crm_admin.codex_mcp import _review_proposal


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "hermes_shared" / "ledger" / "proposals.json"
TARGETS = ROOT / "hermes_shared" / "artifacts" / "CRM-003_p1_contact_company_candidates.csv"
EXPECTED_HASH = "48c06c62b1f384d078d5037dde0f3d6b41e570f19b0e77a6e1253681de71574f"
REVISED_TARGETS = ROOT / "hermes_shared" / "artifacts" / "CRM-003_remaining_revalidated_unapproved.csv"
REVISED_HASH = "85e1804eb99321f273c90e1835894bf252d87e0ad14c13a21b05ec4376592be6"
GENERIC_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com",
    "live.com", "msn.com", "icloud.com", "me.com", "mac.com", "aol.com",
    "protonmail.com", "proton.me", "pm.me", "gmx.com", "mail.com",
}


class CRM003LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.proposals = {item["proposal_id"]: item for item in ledger["proposals"]}
        with TARGETS.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_crm002_is_reconciled_before_crm003(self):
        proposal = self.proposals["CRM-002"]
        self.assertEqual(proposal["status"], "executed")
        self.assertTrue(proposal["execution_authorized"])
        self.assertEqual(len(proposal["outcomes"]), 4)
        self.assertTrue(all(item["status"] == "successful" for item in proposal["outcomes"]))

    def test_crm003_artifact_checksum_population_and_amount(self):
        self.assertEqual(hashlib.sha256(TARGETS.read_bytes()).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.rows), 7)
        self.assertEqual(len({row["contact_id"] for row in self.rows}), 7)
        self.assertEqual(sum(Decimal(row["contact_linked_crm_deal_amount"]) for row in self.rows), Decimal("657457.00"))

    def test_every_target_has_strict_domain_evidence_and_no_association(self):
        valid_domain = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
        for row in self.rows:
            self.assertEqual(row["email_domain"], row["company_domain"])
            self.assertRegex(row["email_domain"], valid_domain)
            self.assertNotIn(row["email_domain"], GENERIC_DOMAINS)
            self.assertEqual(row["exact_domain_company_count"], "1")
            self.assertEqual(row["current_contact_company_count"], "0")
            self.assertGreater(int(row["active_value_deal_count"]), 0)
            self.assertEqual(row["evidence_status"], "deterministic_unique_exact_domain")

    def test_primary_policy_and_rollback_are_guarded(self):
        for row in self.rows:
            self.assertEqual(row["proposed_association_label"], "Primary")
            self.assertIn("zero company associations", row["primary_association_policy"])
            self.assertIn(row["contact_id"], row["rollback_instructions"])
            self.assertIn(row["proposed_company_id"], row["rollback_instructions"])
            self.assertEqual(row["execution_authorized"], "false")

    def test_crm003_requires_explicit_approval_and_authorizes_nothing(self):
        proposal = self.proposals["CRM-003"]
        review = _review_proposal(proposal)
        self.assertEqual(review["decision"], "ready_for_explicit_approval")
        self.assertFalse(review["execution_authorized"])
        self.assertFalse(proposal["execution_authorized"])
        self.assertEqual(proposal["status"], "partially_executed")
        self.assertIn("completed subset only", proposal["approval"]["approved_by"])
        self.assertIn("No remaining contact is approved", proposal["approval"]["scope"])
        self.assertIn("No names, deal titles, LinkedIn, or web research are used.", proposal["evidence"]["matching_rule"])

    def test_crm003_reconciliation_and_revised_unapproved_artifact(self):
        proposal = self.proposals["CRM-003"]
        statuses = [item["status"] for item in proposal["outcomes"]]
        self.assertEqual(statuses.count("successful"), 3)
        self.assertEqual(statuses.count("validation_drift"), 1)
        self.assertEqual(statuses.count("unexecuted"), 3)
        self.assertEqual(hashlib.sha256(REVISED_TARGETS.read_bytes()).hexdigest(), REVISED_HASH)
        with REVISED_TARGETS.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual({row["contact_id"] for row in rows}, {"183833254922", "148465780557", "185166577485"})
        self.assertTrue(all(row["approval_status"] == "unapproved" for row in rows))
        self.assertTrue(all(row["execution_authorized"] == "false" for row in rows))
        self.assertNotIn("55246214682", {row["contact_id"] for row in rows})


if __name__ == "__main__":
    unittest.main()
