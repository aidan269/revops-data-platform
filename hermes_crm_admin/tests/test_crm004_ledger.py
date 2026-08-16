import csv
import hashlib
import json
import unittest
from collections import Counter
from decimal import Decimal
from pathlib import Path

from hermes_crm_admin.codex_mcp import _review_proposal


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "hermes_shared" / "ledger" / "proposals.json"
TARGETS = ROOT / "hermes_shared" / "artifacts" / "CRM-004_active_pipeline_hygiene_queue.csv"
METHODOLOGY = ROOT / "hermes_shared" / "methodologies" / "CRM-004_active_pipeline_hygiene.md"
EXPECTED_HASH = "667e3823ec407b7f75e302866ac803b12757521e4c5b251583ad229c463f9383"


class CRM004LedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.proposal = next(item for item in ledger["proposals"] if item["proposal_id"] == "CRM-004")
        with TARGETS.open(newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_exact_artifact_checksum_count_amount_and_priority(self):
        self.assertEqual(hashlib.sha256(TARGETS.read_bytes()).hexdigest(), EXPECTED_HASH)
        self.assertEqual(len(self.rows), 330)
        self.assertEqual(len({row["deal_id"] for row in self.rows}), 330)
        self.assertEqual(sum(Decimal(row["crm_deal_amount"] or "0") for row in self.rows), Decimal("6140080.60"))
        self.assertEqual(Counter(row["priority"] for row in self.rows), {
            "P0_high_value_close_risk": 26, "P1_close_date_urgent": 279,
            "P2_high_value": 10, "P3_standard": 15,
        })

    def test_unavailable_fields_are_not_fabricated_as_gaps(self):
        fields = [
            "deal_owner_gap_status", "next_step_gap_or_staleness_status",
            "product_service_gap_status", "billing_model_gap_status",
        ]
        for row in self.rows:
            for field in fields:
                self.assertEqual(row[field], "unavailable_in_warehouse_extract_not_scored")

    def test_only_observable_gap_types_are_emitted(self):
        allowed = {
            "close_date_missing", "close_date_past",
            "close_date_implausible_before_deal_created",
            "close_date_implausible_more_than_730_days_future",
            "blank_deal_source", "missing_direct_company_association",
        }
        for row in self.rows:
            gaps = set(row["observable_gaps"].split("; "))
            self.assertTrue(gaps)
            self.assertTrue(gaps <= allowed)
            self.assertEqual(int(row["observable_gap_count"]), len(gaps))

    def test_deal_source_remains_blank_without_approved_deterministic_evidence(self):
        blank_rows = [row for row in self.rows if "blank_deal_source" in row["observable_gaps"]]
        self.assertEqual(len(blank_rows), 320)
        self.assertTrue(all(row["review_only_deal_source_candidate"] == "" for row in blank_rows))
        self.assertTrue(all(row["deal_source_gap_status"] == "remain_blank_no_approved_deterministic_evidence" for row in blank_rows))

    def test_every_item_is_owner_facing_read_only_and_actionable(self):
        for row in self.rows:
            self.assertTrue(row["recommended_human_owner"])
            self.assertTrue(row["recommended_human_action"])
            self.assertEqual(row["execution_authorized"], "False")

    def test_proposal_is_unapproved_and_methodology_is_durable(self):
        self.assertTrue(METHODOLOGY.is_file())
        self.assertEqual(self.proposal["status"], "proposed")
        self.assertFalse(self.proposal["execution_authorized"])
        self.assertIsNone(self.proposal["approval"]["approved_by"])
        self.assertEqual(_review_proposal(self.proposal)["decision"], "ready_for_explicit_approval")


if __name__ == "__main__":
    unittest.main()
