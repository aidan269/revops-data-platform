import csv
import hashlib
import json
import unittest
from pathlib import Path

from hermes_crm_admin.codex_mcp import _review_proposal


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "hermes_shared" / "artifacts" / "CRM-006_p0_active_pipeline_review.csv"
METHODOLOGY = ROOT / "hermes_shared" / "methodologies" / "CRM-006_p0_active_pipeline_review.md"
LEDGER = ROOT / "hermes_shared" / "ledger" / "proposals.json"
EXPECTED_HASH = "4fb4f1e031fd2af666d6bc5ca4f8550dd90a340036ab2fcde2954996838c5991"


class CRM006P0ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with ARTIFACT.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.proposal = next(item for item in ledger["proposals"] if item["proposal_id"] == "CRM-006")

    def test_exact_packet_is_stable_and_has_26_unique_deals(self):
        self.assertEqual(hashlib.sha256(ARTIFACT.read_bytes()).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.rows), 26)
        self.assertEqual(len({row["deal_id"] for row in self.rows}), 26)

    def test_required_review_fields_are_present_without_fabrication(self):
        required = {
            "deal_id", "deal_name", "amount", "stage", "close_date",
            "current_owner_id", "next_step", "product_service", "billing_model",
            "evidence_bound_review_action",
        }
        self.assertTrue(required <= set(self.rows[0]))
        self.assertTrue(all(row["deal_name"] == "Unavailable in current warehouse snapshot" for row in self.rows))
        self.assertTrue(all(row["current_owner_id"] for row in self.rows))

    def test_owner_names_are_explicitly_unavailable(self):
        self.assertTrue(all(not row["owner_name"] for row in self.rows))
        self.assertTrue(all(row["owner_name_mapping_status"] == "unavailable_no_owner_dimension" for row in self.rows))

    def test_actions_separate_observation_from_human_request(self):
        for row in self.rows:
            action = row["evidence_bound_review_action"]
            self.assertIn("Observed:", action)
            self.assertIn("Requested human action:", action)
            self.assertIn("no value is proposed", action)
            self.assertEqual(row["execution_authorized"], "False")

    def test_proposal_is_read_only_and_unapproved(self):
        self.assertTrue(METHODOLOGY.is_file())
        self.assertEqual(self.proposal["status"], "proposed")
        self.assertFalse(self.proposal["execution_authorized"])
        self.assertIsNone(self.proposal["approval"]["approved_by"])
        self.assertEqual(_review_proposal(self.proposal)["decision"], "ready_for_explicit_approval")


if __name__ == "__main__":
    unittest.main()
