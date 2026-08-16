import json
import tempfile
import unittest
from pathlib import Path

from hermes_shared.execution_events import append_execution_event, validate_event


class ExecutionEventTests(unittest.TestCase):
    def test_append_preserves_existing_bytes_and_adds_one_json_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            original = b'{"existing":true}\n'
            path.write_bytes(original)
            event = append_execution_event(
                proposal_id="CRM-TEST", item_type="contact", item_id="123",
                action="proposal_created", status="proposed",
                evidence_reference="artifact.csv#sha256:abc",
                message="Created an evidence-bound proposal; no CRM action occurred.",
                event_path=path, timestamp="2026-08-09T00:00:00Z",
            )
            content = path.read_bytes()
            self.assertTrue(content.startswith(original))
            self.assertEqual(content.count(b"\n"), 2)
            self.assertEqual(json.loads(content.splitlines()[-1]), event)

    def test_each_call_appends_exactly_one_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            for item_id in ("1", "2"):
                append_execution_event(
                    proposal_id="CRM-TEST", item_type="deal", item_id=item_id,
                    action="reconcile", status="successful",
                    evidence_reference="ledger/proposals.json",
                    message=f"Reconciled item {item_id}; no CRM action occurred.",
                    event_path=path,
                )
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual([json.loads(line)["item_id"] for line in lines], ["1", "2"])

    def test_rejects_missing_fields_and_unsafe_identifiers(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            validate_event({})
        with self.assertRaisesRegex(ValueError, "safe identifier"):
            append_execution_event(
                proposal_id="CRM 003", item_type="contact", item_id="1",
                action="proposal", status="proposed", evidence_reference="artifact",
                message="Safe message.", event_path=Path("/unused"),
            )

    def test_rejects_secret_bearing_messages(self):
        with self.assertRaisesRegex(ValueError, "credential"):
            append_execution_event(
                proposal_id="CRM-TEST", item_type="contact", item_id="1",
                action="proposal", status="proposed", evidence_reference="artifact",
                message="Authorization: Bearer secret", event_path=Path("/unused"),
            )

    def test_allows_bare_environment_variable_names_without_values(self):
        event = validate_event({
            "timestamp": "2026-08-09T00:00:00Z", "proposal_id": "CRM-TEST",
            "item_type": "preflight", "item_id": "credential_presence",
            "action": "verify", "status": "successful",
            "evidence_reference": "local-environment",
            "message": "HUBSPOT_PRIVATE_APP_TOKEN was present; its value was not logged.",
        })
        self.assertEqual(event["status"], "successful")

    def test_repository_feed_contains_valid_jsonl_events(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "hermes_shared" / "ledger" / "execution_events.jsonl"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertGreaterEqual(len(lines), 1)
        for line in lines:
            self.assertEqual(validate_event(json.loads(line)), json.loads(line))


if __name__ == "__main__":
    unittest.main()
