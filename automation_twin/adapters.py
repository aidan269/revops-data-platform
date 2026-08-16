"""Source adapters: import existing repository/warehouse evidence into the canonical graph.

Deterministic and idempotent. No adapter calls a write-capable external tool.
Surfaces that were never collected become NOT_COLLECTED snapshots and, where
prior evidence proves an asset exists, unresolved asset stubs with no invented
nodes or edges.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .model import (COLLECTED, NOT_COLLECTED, PARTIAL, INFERRED, OBSERVED,
                    Asset, Edge, FieldAccess, Graph, Node, Snapshot, stable_id)

from .config import artifact_root, ledger_path

ROOT = Path(__file__).resolve().parents[1]
def _now() -> str:
    """Actual collection time. Never a frozen literal."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def collection_run_id(graph_sources: list[str]) -> str:
    """Identity of one collection run, derived from the evidence actually present."""
    return stable_id("collection", *sorted(graph_sources))


def ART() -> Path:
    """Artifact/evidence root. Configurable via REVOPS_ARTIFACT_ROOT."""
    return artifact_root()


def LEDGER() -> Path:
    """Audit ledger path. Configurable via REVOPS_LEDGER_PATH."""
    return ledger_path()


def _hash_file(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _snap(graph, system, artifact, *, workspace=None, collector="repository_artifact",
          status=COLLECTED, baseline=True, reason=None) -> Snapshot:
    path = ART() / artifact if artifact and not artifact.startswith("/") else None
    digest = _hash_file(path) if path else None
    if status == NOT_COLLECTED:
        baseline = False
    s = Snapshot(
        snapshot_id=stable_id("snap", system, artifact, digest or "absent"),
        source_system=system, workspace_identifier=workspace,
        collected_at=_now(), collector=collector, source_artifact=artifact,
        source_hash=digest, collection_status=status,
        baseline_established=baseline, not_collected_reason=reason,
    )
    graph.snapshots.append(s)
    return s


def _rows(name: str) -> list[dict]:
    p = ART() / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
def forms_adapter(graph: Graph) -> None:
    """CRM-013 form estate: 111 forms, fully collected."""
    art = "CRM-013_forms.csv"
    rows = _rows(art)
    s = _snap(graph, "forms", art, workspace="46025408",
              status=COLLECTED if rows else NOT_COLLECTED, baseline=bool(rows),
              reason=None if rows else "CRM-013 artifact absent")
    for r in rows:
        aid = stable_id("forms", r["form_id"])
        graph.assets.append(Asset(
            asset_id=aid, snapshot_id=s.snapshot_id, source_system="forms",
            native_id=r["form_id"], name=r["form_name"], asset_type="form",
            object_type="FORM",
            state="active" if r.get("activity_state") == "active" else "unknown",
            owner_identity=None, evidence_state=COLLECTED,
            last_observed=r.get("observed_at") or _now(), raw_definition_ref=art,
        ))


def hubspot_adapter(graph: Graph) -> None:
    """HubSpot workflows: production creators are known; definitions were never collected."""
    art = "CRM-020_manifest.json"
    s = _snap(graph, "hubspot", art, workspace="46025408", status=PARTIAL, baseline=False)
    # Assets proven to exist by prior evidence. Definitions NOT_COLLECTED -> no nodes/edges invented.
    known = [
        ("1858050407", "MASTER | Offer | Create & Assign Deal", "active", COLLECTED),
        ("1775787045", "Contact Us Inquiry Forms (Current)", "active", COLLECTED),
        ("1833911074", "MASTER | Campaign | Set Deal Primary Campaign Source", "active", COLLECTED),
        ("1865190481", "DRAFT | Intake | Web2 Demo -> Deal", "draft", COLLECTED),
        ("1865189681", "DRAFT | Intake | Contact Us -> Deal Field Sync", "draft", COLLECTED),
        ("1865239693", "DO NOT ACTIVATE | Superseded Web3 Clone", "off", COLLECTED),
        ("1865239106", "CRM-018 forward attribution draft", "off", PARTIAL),
        ("590100350", "Sales > CS: Next Steps", "off", PARTIAL),
    ]
    for native, name, state, ev in known:
        graph.assets.append(Asset(
            asset_id=f"hubspot:workflow:{native}", snapshot_id=s.snapshot_id,
            source_system="hubspot", native_id=native, name=name, asset_type="workflow",
            object_type="DEAL", state=state, owner_identity=None, evidence_state=ev,
            last_observed=_now(), raw_definition_ref=art,
        ))
    # The 161-workflow estate itself was never baselined.
    _snap(graph, "hubspot", "hubspot_workflow_estate", workspace="46025408",
          collector="browser_report", status=NOT_COLLECTED, baseline=False,
          reason="161 workflows reported in browser; no MCP or API surface collected their definitions")

    # Observed field access, from CRM-020 production configuration.
    def fa(asset, prop, overwrite, basis, conf, note):
        graph.field_access.append(FieldAccess(
            access_id=stable_id("fa", asset, prop), asset_id=asset, node_id=None,
            system="hubspot", object_type="DEAL", property_name=prop, operation="write",
            overwrite_behavior=overwrite, conditional_behavior=note, basis=basis,
            confidence=conf, evidence_reference=art))
    fa("hubspot:workflow:1858050407", "dealname", "replace", OBSERVED, "high", "{Company Name} - Demo")
    fa("hubspot:workflow:1858050407", "requested_service", "replace", OBSERVED, "high", None)
    fa("hubspot:workflow:1858050407", "self_declared_attribution", "replace", OBSERVED, "high", None)
    fa("hubspot:workflow:1858050407", "brief_project_description", "replace", OBSERVED, "high", "copied from enrolled contact during deal creation")
    fa("hubspot:workflow:1775787045", "requested_service", "replace", OBSERVED, "high", None)
    fa("hubspot:workflow:1775787045", "brief_project_description", "replace", OBSERVED, "high", None)
    graph.field_access.append(FieldAccess(
        access_id=stable_id("fa", "1833911074", "primary_campaign_source"),
        asset_id="hubspot:workflow:1833911074", node_id=None, system="hubspot",
        object_type="CONTACT", property_name="primary_campaign_source", operation="write",
        overwrite_behavior="replace", conditional_behavior="copies Latest Campaign Source",
        basis=OBSERVED, confidence="high", evidence_reference="CRM-017 addendum"))


def apollo_adapter(graph: Graph) -> None:
    """Apollo: MCP-collected assets plus explicitly NOT_COLLECTED admin surfaces."""
    art = "APOLLO-INFRA-BASELINE_manifest.json"
    team = "6a04fc8ce0409a001dd5728f"
    s = _snap(graph, "apollo", art, workspace=team, collector="mcp", status=PARTIAL, baseline=False)
    manifest = {}
    p = ART() / art
    if p.exists():
        manifest = json.loads(p.read_text(encoding="utf-8"))
    counts = manifest.get("counts", {})
    graph.assets.append(Asset(
        asset_id="apollo:list_set", snapshot_id=s.snapshot_id, source_system="apollo",
        native_id=team, name=f"{counts.get('lists', 0)} Apollo lists", asset_type="list",
        object_type="CONTACT/ACCOUNT", state="active", owner_identity=None,
        evidence_state=COLLECTED, last_observed=_now(), raw_definition_ref=art))
    graph.assets.append(Asset(
        asset_id="apollo:sequence_set", snapshot_id=s.snapshot_id, source_system="apollo",
        native_id=team, name=f"{counts.get('sequences', 0)} sequences (all inactive, zero sends)",
        asset_type="sequence", object_type="CONTACT", state="off",
        owner_identity="mohammad@spearbit.com", evidence_state=COLLECTED,
        last_observed=_now(), raw_definition_ref=art))
    graph.assets.append(Asset(
        asset_id="apollo:mailbox", snapshot_id=s.snapshot_id, source_system="apollo",
        native_id="6a39466483028f00148e7ef2", name="linked mailbox", asset_type="integration",
        object_type=None, state="active", owner_identity="mohammad@spearbit.com",
        evidence_state=COLLECTED, last_observed=_now(), raw_definition_ref=art))
    # Browser-reported integration. Source and timestamp preserved; not promoted to MCP-confirmed.
    bs = _snap(graph, "apollo", "apollo_hubspot_integration", workspace=team,
               collector="browser_report", status=PARTIAL, baseline=False)
    graph.assets.append(Asset(
        asset_id="apollo:integration:hubspot", snapshot_id=bs.snapshot_id,
        source_system="apollo", native_id="hubspot", name="Apollo-HubSpot integration",
        asset_type="integration", object_type=None, state="active",
        owner_identity="aidan@spearbit.com", evidence_state=PARTIAL,
        last_observed=_now(),
        raw_definition_ref="browser_report:default_settings warning visible 2026-08-12"))
    for surface, reason in (
        ("apollo_imports", "Apollo MCP exposes no import/export administration surface"),
        ("apollo_field_mappings", "Apollo MCP exposes no HubSpot field mapping or sync rules"),
        ("apollo_error_logs", "Apollo MCP exposes no error-log surface"),
        ("apollo_user_directory", "Apollo MCP exposes no user directory"),
        ("apollo_enrichment_schedules", "Apollo MCP exposes no enrichment schedules"),
    ):
        _snap(graph, "apollo", surface, workspace=team, collector="mcp",
              status=NOT_COLLECTED, baseline=False, reason=reason)


def zapier_adapter(graph: Graph) -> None:
    """Zapier: definitions never collected. Stubs only for Zaps prior evidence proves exist."""
    _snap(graph, "zapier", "zapier_zap_definitions", collector="browser_report",
          status=NOT_COLLECTED, baseline=False,
          reason="25 Zaps reported in browser; MCP exposes only Zapier Manager with 0 connections")
    s = _snap(graph, "zapier", "zapier_known_zaps", collector="browser_report",
              status=PARTIAL, baseline=False)
    for native, name in (
        ("285219462", "Webflow Form Submission -> HS"),
        ("290224990", "channel lead > Hubspot"),
        ("261390989", "Hubspot: Kickoff Slides & Onboarding Doc Generator"),
        ("354871728", "Clarion<>CantinaBBP"),
        ("287456304", "Avon NDA: Airtable Signup Sends Docusign NDA"),
    ):
        graph.assets.append(Asset(
            asset_id=f"zapier:zap:{native}", snapshot_id=s.snapshot_id, source_system="zapier",
            native_id=native, name=name, asset_type="zap", object_type=None,
            state="active", owner_identity=None, evidence_state=NOT_COLLECTED,
            last_observed=_now(),
            raw_definition_ref="CRM-013 browser inventory; definition NOT_COLLECTED"))
        # Unresolved edge: the Zap is known to reach HubSpot, but no node detail exists.
        graph.edges.append(Edge(
            edge_id=stable_id("edge", "zapier", native, "hubspot"),
            asset_id=f"zapier:zap:{native}", source_node_id=None, target_node_id=None,
            source_ref=f"zapier:zap:{native}", target_ref="hubspot:portal:46025408",
            branch_condition=None, path_type="normal", basis=INFERRED,
            evidence_reference="Zap name indicates a HubSpot destination; definition NOT_COLLECTED",
            endpoints_resolved=False))


def warehouse_adapter(graph: Graph, database_url: str | None = None) -> None:
    """Load attribution evidence only when its recorded artifact is actually present."""
    art = "CRM-017_manifest.json"
    present = (ART() / art).exists()
    if not present:
        _snap(graph, "warehouse", art, workspace="46025408", collector="warehouse",
              status=NOT_COLLECTED, baseline=False,
              reason=("CRM-017 evidence artifact not present in the configured artifact root; "
                      "prior contamination counts are NOT reconstructed from memory"))
        return

    s = _snap(graph, "warehouse", art, workspace="46025408", collector="warehouse",
              status=COLLECTED, baseline=True)
    manifest = json.loads((ART() / art).read_text(encoding="utf-8"))
    counts = manifest.get("population", {}) or {}
    contaminated = counts.get("total_contaminated_contacts")
    graph.assets.append(Asset(
        asset_id="hubspot:property:primary_campaign_source", snapshot_id=s.snapshot_id,
        source_system="hubspot", native_id="primary_campaign_source",
        name="Primary Campaign Source", asset_type="property", object_type="CONTACT",
        state="active", owner_identity=None, evidence_state=COLLECTED,
        last_observed=_now(), raw_definition_ref=art))
    graph.assets.append(Asset(
        asset_id="hubspot:import:unidentified_writer", snapshot_id=s.snapshot_id,
        source_system="hubspot", native_id=None,
        name="unidentified writer of vendor values into Primary Campaign Source",
        asset_type="import", object_type="CONTACT", state="unknown", owner_identity=None,
        evidence_state=PARTIAL, last_observed=_now(), raw_definition_ref=art))
    detail = (f"{contaminated} contacts carried vendor literals per {art}"
              if contaminated is not None else
              f"vendor literals recorded in {art}; count not present in the artifact")
    graph.field_access.append(FieldAccess(
        access_id=stable_id("fa", "unidentified", "primary_campaign_source"),
        asset_id="hubspot:import:unidentified_writer", node_id=None, system="hubspot",
        object_type="CONTACT", property_name="primary_campaign_source", operation="write",
        overwrite_behavior="unknown",
        conditional_behavior=f"prior recorded evidence ({art}): {detail}",
        basis=OBSERVED, confidence="high", evidence_reference=art))
    graph.edges.append(Edge(
        edge_id=stable_id("edge", "apollo", "hubspot_import"),
        asset_id="apollo:list_set", source_node_id=None, target_node_id=None,
        source_ref="apollo:list_set", target_ref="hubspot:import:unidentified_writer",
        branch_condition=None, path_type="normal", basis=INFERRED,
        evidence_reference=f"prior recorded evidence ({art}): Apollo list names match HubSpot import source files",
        endpoints_resolved=True))


def ledger_adapter(graph: Graph) -> None:
    """Audit ledger provenance: counts only, no message contents copied."""
    lp = LEDGER()
    digest = _hash_file(lp)
    lines = sum(1 for ln in lp.read_text(encoding="utf-8").splitlines() if ln.strip()) \
        if lp.exists() else 0
    if not lp.exists():
        _snap(graph, "ledger", "hermes_shared/ledger/execution_events.jsonl",
              collector="repository_artifact", status=NOT_COLLECTED, baseline=False,
              reason="audit ledger not present in this checkout; it is operational evidence and is not committed")
        return
    s = Snapshot(
        snapshot_id=stable_id("snap", "ledger", "execution_events", digest or "absent"),
        source_system="ledger", workspace_identifier=None, collected_at=_now(),
        collector="repository_artifact", source_artifact="hermes_shared/ledger/execution_events.jsonl",
        source_hash=digest, collection_status=COLLECTED, baseline_established=True)
    graph.snapshots.append(s)
    graph.assets.append(Asset(
        asset_id="ledger:execution_events", snapshot_id=s.snapshot_id, source_system="ledger",
        native_id=None, name=f"audit ledger ({lines} valid lines)", asset_type="integration",
        object_type=None, state="active", owner_identity=None, evidence_state=COLLECTED,
        last_observed=_now(), raw_definition_ref="execution_events.jsonl"))


ADAPTERS = (forms_adapter, hubspot_adapter, apollo_adapter, zapier_adapter,
            warehouse_adapter, ledger_adapter)


def build_graph() -> Graph:
    """Deterministic, idempotent construction of the full evidence graph."""
    g = Graph()
    for adapter in ADAPTERS:
        adapter(g)
    return g
