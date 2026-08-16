import csv
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXTRACTOR_PATH = ROOT / "extract" / "extract_deals.py"
POST_QUEUE = ROOT / "hermes_shared" / "artifacts" / "CRM-004_post_CRM-005_readiness_queue.csv"
POST_QUEUE_HASH = "414bc3e345fa9bded9fdca83dad47fe43ae0b52c69ba046b5d631a81d3fbb3af"
LINEAGE = ROOT / "hermes_shared" / "methodologies" / "CRM-005_deal_extraction_lineage.md"


def load_extractor():
    specification = importlib.util.spec_from_file_location("crm005_extract_deals", EXTRACTOR_PATH)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class CRM005ReadinessTests(unittest.TestCase):
    def test_canonicalizer_preserves_nulls_and_sets_provenance(self):
        extractor = load_extractor()
        result = extractor.canonicalize_crm_admin_fields({
            "hubspot_owner_id": "owner-1", "hs_next_step": "",
        })
        self.assertTrue(result["_crm_admin_fields_extracted"])
        self.assertEqual(result["_crm_admin_deal_owner_id"], "owner-1")
        self.assertIsNone(result["_crm_admin_next_step"])
        self.assertIsNone(result["_crm_admin_product_service"])
        self.assertIsNone(result["_crm_admin_billing_model"])

    def test_requested_properties_omit_unconfigured_names(self):
        extractor = load_extractor()
        requested = extractor.requested_deal_properties()
        self.assertNotIn("", requested)
        self.assertIn("hubspot_owner_id", requested)
        self.assertIn("hs_next_step", requested)

    def test_post_readiness_queue_is_exact_and_provenance_safe(self):
        self.assertEqual(hashlib.sha256(POST_QUEUE.read_bytes()).hexdigest(), POST_QUEUE_HASH)
        with POST_QUEUE.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 330)
        self.assertTrue(all(row["crm_admin_fields_extracted"] == "False" for row in rows))
        status_fields = [
            "deal_owner_gap_status", "next_step_gap_or_staleness_status",
            "product_service_gap_status", "billing_model_gap_status",
        ]
        for row in rows:
            for field in status_fields:
                self.assertEqual(row[field], "unavailable_in_current_snapshot_not_scored")

    def test_crm005_ledger_is_read_only_and_lineage_is_documented(self):
        ledger = json.loads((ROOT / "hermes_shared" / "ledger" / "proposals.json").read_text())
        proposal = next(item for item in ledger["proposals"] if item["proposal_id"] == "CRM-005")
        self.assertFalse(proposal["execution_authorized"])
        self.assertTrue(LINEAGE.is_file())
        self.assertIn("does not run a HubSpot", LINEAGE.read_text())


if __name__ == "__main__":
    unittest.main()
