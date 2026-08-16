"""AUTOMATION-DIGITAL-TWIN — safety, determinism and simulation tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation_twin.adapters import build_graph                      # noqa: E402
from automation_twin.fixtures import FIXTURES                          # noqa: E402
from automation_twin.model import NOT_COLLECTED, Snapshot              # noqa: E402
from automation_twin import policy                                     # noqa: E402
from automation_twin.provenance_contract import LEAD_DATA_PROVIDER_CONTRACT  # noqa: E402
from automation_twin.simulator import simulate                         # noqa: E402


@pytest.fixture(scope="module")
def graph():
    return build_graph()


# ---------------- imports: deterministic, idempotent, honest ----------------
def test_import_is_deterministic_and_idempotent():
    a, b = build_graph(), build_graph()
    assert [x.asset_id for x in a.assets] == [x.asset_id for x in b.assets]
    assert [x.edge_id for x in a.edges] == [x.edge_id for x in b.edges]
    assert [x.snapshot_id for x in a.snapshots] == [x.snapshot_id for x in b.snapshots]


def test_stable_ids_are_unique(graph):
    for coll, key in ((graph.assets, "asset_id"), (graph.edges, "edge_id"),
                      (graph.snapshots, "snapshot_id"), (graph.field_access, "access_id")):
        ids = [getattr(x, key) for x in coll]
        assert len(ids) == len(set(ids)), f"duplicate {key}"


def test_referential_integrity(graph):
    assert graph.validate() == []


def test_not_collected_surface_cannot_claim_a_baseline():
    with pytest.raises(ValueError):
        Snapshot(snapshot_id="x", source_system="apollo", workspace_identifier=None,
                 collected_at="2026-08-12T00:00:00Z", collector="mcp",
                 source_artifact="a", source_hash=None,
                 collection_status=NOT_COLLECTED, baseline_established=True,
                 not_collected_reason="r")


def test_not_collected_requires_a_reason():
    with pytest.raises(ValueError):
        Snapshot(snapshot_id="x", source_system="apollo", workspace_identifier=None,
                 collected_at="2026-08-12T00:00:00Z", collector="mcp",
                 source_artifact="a", source_hash=None,
                 collection_status=NOT_COLLECTED, baseline_established=False)


def test_inaccessible_surfaces_are_present_and_not_empty_successes(graph):
    """Fix 5 — Apollo admin + Zap definitions must be NOT_COLLECTED, never zero-row healthy."""
    nc = {s.source_artifact for s in graph.snapshots if s.collection_status == NOT_COLLECTED}
    assert "apollo_imports" in nc
    assert "apollo_field_mappings" in nc
    assert "apollo_error_logs" in nc
    assert "zapier_zap_definitions" in nc
    for s in graph.snapshots:
        if s.collection_status == NOT_COLLECTED:
            assert s.baseline_established is False
            assert s.not_collected_reason


def test_zap_stubs_have_no_invented_nodes(graph):
    zap_assets = {a.asset_id for a in graph.assets if a.source_system == "zapier"}
    assert zap_assets, "known Zaps should exist as stubs"
    assert not [n for n in graph.nodes if n.asset_id in zap_assets], "no nodes may be invented"
    for a in graph.assets:
        if a.source_system == "zapier":
            assert a.evidence_state == NOT_COLLECTED


def test_observation_and_inference_stay_separate(graph):
    assert {e.basis for e in graph.edges} <= {"observed", "inferred"}
    inferred = [e for e in graph.edges if e.basis == "inferred"]
    assert inferred and all(e.evidence_reference for e in inferred)


def test_no_evidence_row_authorizes_an_external_write(graph):
    for coll in (graph.assets, graph.nodes, graph.edges, graph.field_access, graph.snapshots):
        assert all(getattr(x, "authorizes_external_write") is False for x in coll)


# ---------------- protected-field guardrails (Fix 1 / Fix 3) ----------------
@pytest.mark.parametrize("column", [
    "vendor", "provider", "enriched_by", "data_source", "source_file", "tool",
    "provenance", "supplied_by", "Email Source", "found_by", "bhf.csv",
])
def test_provenance_columns_are_rejected_for_protected_fields(column):
    assert not policy.validate_import_mapping(column, "Primary Campaign Source").allowed


def test_blackhat_contamination_pattern_is_reproduced_and_blocked():
    """The exact shape observed in blackhat2: one file, five vendor literals."""
    vendors = ["Apollo", "Findymail", "LeadMagic", "Prospeo", "Icypeas"]
    verdict = policy.validate_sample_values("Primary Campaign Source", vendors)
    assert not verdict.allowed
    for v in vendors:
        assert v in verdict.finding


def test_mapping_fails_closed_on_unknown_column():
    v = policy.validate_import_mapping("Campaign Name", "Primary Campaign Source")
    assert not v.allowed and "fail-closed" in v.finding


def test_unprotected_destination_is_allowed():
    assert policy.validate_import_mapping("Notes", "Description").allowed


def test_validator_never_mutates_input():
    col, dest = "vendor", "Primary Campaign Source"
    policy.validate_import_mapping(col, dest)
    assert (col, dest) == ("vendor", "Primary Campaign Source")


def test_apollo_is_not_a_registered_writer_of_campaign_source():
    assert not policy.validate_writer("apollo:integration:hubspot", "Primary Campaign Source").allowed
    assert "apollo" not in str(policy.APPROVED_PROTECTED_WRITERS["primary_campaign_source"]).lower()


def test_protected_field_set_covers_required_fields():
    for f in ("primary_campaign_source", "latest_campaign_source", "deal_source", "repo_uri"):
        assert f in policy.PROTECTED_FIELDS


# ---------------- evidence honesty ----------------
def test_apollo_is_not_labelled_the_confirmed_writer(graph):
    apollo = [a for a in graph.assets if a.source_system == "apollo"]
    assert apollo
    for fa in graph.field_access:
        if fa.property_name == "primary_campaign_source":
            assert not fa.asset_id.startswith("apollo:"), "Apollo must not be a confirmed writer"
    inferred = [e for e in graph.edges if e.source_ref == "apollo:list_set"]
    assert inferred and all(e.basis == "inferred" for e in inferred)


def test_zapier_is_not_labelled_the_overwrite_cause(graph):
    findings = policy.run_policies(graph)
    for f in findings:
        blob = f"{f.observation} {f.inference or ''}".lower()
        if "overwrite" in blob or "contamin" in blob:
            assert "zapier" not in blob, "Zapier must not be named as the overwrite cause"


# ---------------- simulation ----------------
def test_simulation_proposes_but_never_executes():
    r = simulate(FIXTURES["valid_campaign_propagation"])
    assert r["proposed_writes"] and r["externally_executed"] is False


def test_vendor_contamination_is_blocked_in_simulation():
    r = simulate(FIXTURES["vendor_contamination_attempt"])
    assert r["proposed_writes"] == []
    assert any(b["disposition"] == "would_conflict" for b in r["blocked_writes"])


def test_multi_target_ambiguity_stops_safely():
    r = simulate(FIXTURES["multi_deal_ambiguity"])
    assert r["result"] == "stopped_safe"
    assert any(e["code"] == "AMBIGUOUS_TARGET" for e in r["exceptions"])
    assert r["proposed_writes"] == []


def test_missing_association_stops_safely():
    r = simulate(FIXTURES["missing_associated_contact"])
    assert r["result"] == "stopped_safe"
    assert any(e["code"] == "NO_TARGET" for e in r["exceptions"])


def test_populated_destination_is_not_overwritten():
    r = simulate(FIXTURES["populated_destination_conflict"])
    assert r["proposed_writes"] == []
    assert any(b["disposition"] == "would_skip" for b in r["blocked_writes"])


def test_absent_source_value_is_cannot_evaluate():
    r = simulate(FIXTURES["deal_created_before_submission"])
    assert any(b["disposition"] == "cannot_evaluate" for b in r["blocked_writes"])


def test_replay_is_idempotent_and_deterministic():
    a = simulate(FIXTURES["valid_campaign_propagation"])
    b = simulate(FIXTURES["valid_campaign_propagation"])
    assert a["fixture_hash"] == b["fixture_hash"]
    assert a["proposed_writes"] == b["proposed_writes"]
    assert a["traversed"] == b["traversed"]


def test_duplicate_creator_replay_is_idempotent():
    r = simulate(FIXTURES["duplicate_creator"])
    assert r["proposed_writes"] == []


def test_approval_interrupt_carries_exact_targets():
    r = simulate(FIXTURES["valid_campaign_propagation"])
    p = r["approval_payload"]
    for key in ("target_system", "asset_id", "records", "fields", "old_values",
                "proposed_values", "reason", "rollback", "idempotency_key",
                "evidence_references"):
        assert key in p, f"approval payload missing {key}"
    assert p["records"] == ["D1"] and p["fields"] == ["primary_campaign_source"]


def test_approved_state_still_cannot_reach_a_production_adapter():
    """Even with approval granted, no executor exists to mutate an external system."""
    r = simulate(FIXTURES["valid_campaign_propagation"])
    r["approval_state"] = "APPROVED"          # simulate a human approving
    policy.assert_no_production_adapter()      # structurally absent
    assert r["externally_executed"] is False


def test_every_fixture_runs_without_external_effect():
    for name in FIXTURES:
        r = simulate(FIXTURES[name])
        assert r["externally_executed"] is False
        assert r["result"] in {"completed", "stopped_safe", "policy_blocked", "cannot_evaluate"}


# ---------------- structural safety ----------------
def test_no_production_write_adapter_module_exists():
    policy.assert_no_production_adapter()


def test_cli_has_no_execute_command():
    from automation_twin import cli
    assert "execute" not in cli.__doc__.split("Commands:")[1].lower().split("\n")[0]
    for forbidden in cli.FORBIDDEN_COMMANDS:
        with pytest.raises(SystemExit):
            cli.main([forbidden])


def test_no_module_imports_a_write_capable_client():
    pkg = ROOT / "automation_twin"
    banned = ("hubspot_client", "requests.post", "requests.put", "requests.patch",
              "requests.delete", "apollo_contacts_create", "apollo_contacts_update",
              "execute_zapier_write_action")
    for path in pkg.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, f"{path.name} references write-capable client {b}"


def test_provenance_contract_is_proposal_only():
    c = LEAD_DATA_PROVIDER_CONTRACT
    assert c["status"] == "PROPOSED_NOT_CREATED"
    assert c["authorizes_external_write"] is False
    assert "never" in c["relationship_to_campaign_attribution"].lower()


def test_fixtures_contain_no_pii():
    blob = json.dumps(FIXTURES).lower()
    for marker in ("@gmail", "@spearbit.com", "@cantina.security", "@mozilla",
                   "firstname", "lastname"):
        assert marker not in blob, f"fixture leaked {marker}"
    assert "@" not in blob.replace("@example.invalid", "")


def test_migration_declares_no_external_authorization():
    sql = (ROOT / "db" / "10_automation_digital_twin.sql").read_text(encoding="utf-8")
    assert "authorizes_external_write = false" in sql
    assert "automation_approvals" in sql
    assert "aap_auth_requires_human_ck" in sql


def test_grants_are_select_only():
    sql = (ROOT / "db" / "11_automation_twin_grants.sql").read_text(encoding="utf-8")
    assert "hermes_reader" in sql and "GRANT SELECT" in sql
    for forbidden in ("GRANT INSERT", "GRANT UPDATE", "GRANT DELETE", "GRANT ALL"):
        assert forbidden not in sql


def test_populated_protected_destination_is_skipped_not_overwritten():
    """A populated protected field under only_if_empty is a no-op, never a write."""
    r = simulate(FIXTURES["populated_destination_conflict"])
    assert r["proposed_writes"] == []
    dispositions = {b["disposition"] for b in r["blocked_writes"]}
    assert dispositions == {"would_skip"}


def test_protected_field_with_replace_still_hits_writer_control():
    """Precedence must not let an overwriting rule bypass the protected-field check."""
    fx = dict(FIXTURES["populated_destination_conflict"])
    fx["rules"] = [{"property": "repo_uri", "value": "https://example.invalid/other",
                    "overwrite": "replace"}]
    r = simulate(fx)
    assert r["proposed_writes"] == []
    assert any(b["disposition"] == "would_conflict" for b in r["blocked_writes"])
