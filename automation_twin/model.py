"""Canonical, vendor-neutral automation model. Pure data; no I/O, no external calls."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any

COLLECTED, PARTIAL, NOT_COLLECTED = "COLLECTED", "PARTIAL", "NOT_COLLECTED"
OBSERVED, INFERRED = "observed", "inferred"


def stable_id(*parts: Any) -> str:
    """Deterministic id from its parts. Same inputs always yield the same id."""
    raw = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def fixture_hash(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass
class Snapshot:
    snapshot_id: str
    source_system: str
    workspace_identifier: str | None
    collected_at: str
    collector: str
    source_artifact: str
    source_hash: str | None
    collection_status: str
    baseline_established: bool
    not_collected_reason: str | None = None
    authorizes_external_write: bool = False

    def __post_init__(self):
        if self.collection_status == NOT_COLLECTED:
            if self.baseline_established:
                raise ValueError(
                    f"{self.snapshot_id}: NOT_COLLECTED surface cannot claim a baseline"
                )
            if not self.not_collected_reason:
                raise ValueError(f"{self.snapshot_id}: NOT_COLLECTED requires a reason")
        if self.authorizes_external_write:
            raise ValueError("evidence never authorizes an external write")


@dataclass
class Asset:
    asset_id: str
    snapshot_id: str
    source_system: str
    native_id: str | None
    name: str | None
    asset_type: str
    object_type: str | None
    state: str
    owner_identity: str | None
    evidence_state: str
    first_observed: str | None = None
    last_observed: str | None = None
    raw_definition_ref: str | None = None
    authorizes_external_write: bool = False

    def __post_init__(self):
        if self.state not in {"active", "off", "draft", "unknown"}:
            raise ValueError(f"{self.asset_id}: bad state {self.state}")
        if self.evidence_state not in {COLLECTED, PARTIAL, NOT_COLLECTED}:
            raise ValueError(f"{self.asset_id}: bad evidence_state")


@dataclass
class Node:
    node_id: str
    asset_id: str
    node_type: str
    operation: str | None
    object_type: str | None
    classification: str
    config: dict = field(default_factory=dict)
    basis: str = OBSERVED
    write_capability: bool = False
    external_side_effect: str = "none"
    authorizes_external_write: bool = False


@dataclass
class Edge:
    edge_id: str
    asset_id: str
    source_node_id: str | None
    target_node_id: str | None
    source_ref: str | None
    target_ref: str | None
    branch_condition: str | None
    path_type: str
    basis: str
    evidence_reference: str | None
    endpoints_resolved: bool = False
    authorizes_external_write: bool = False


@dataclass
class FieldAccess:
    access_id: str
    asset_id: str
    node_id: str | None
    system: str
    object_type: str
    property_name: str
    operation: str
    overwrite_behavior: str | None
    conditional_behavior: str | None
    basis: str
    confidence: str
    evidence_reference: str | None
    authorizes_external_write: bool = False


@dataclass
class Finding:
    finding_id: str
    policy_id: str
    severity: str
    asset_id: str | None
    system: str | None
    object_type: str | None
    property_name: str | None
    observation: str
    inference: str | None
    evidence_reference: str | None
    recurrence_risk: str | None = None
    reversibility: str | None = None
    proposed_remediation: str | None = None
    approval_required: bool = True
    authorizes_external_write: bool = False


@dataclass
class Graph:
    snapshots: list[Snapshot] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    field_access: list[FieldAccess] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def asset_ids(self) -> set[str]:
        return {a.asset_id for a in self.assets}

    def node_ids(self) -> set[str]:
        return {n.node_id for n in self.nodes}

    def validate(self) -> list[str]:
        """Referential integrity. Returns a list of problems; empty means valid."""
        problems: list[str] = []
        snap_ids = {s.snapshot_id for s in self.snapshots}
        seen: set[str] = set()
        for a in self.assets:
            if a.asset_id in seen:
                problems.append(f"duplicate asset_id {a.asset_id}")
            seen.add(a.asset_id)
            if a.snapshot_id not in snap_ids:
                problems.append(f"asset {a.asset_id} references unknown snapshot")
        aids, nids = self.asset_ids(), self.node_ids()
        for n in self.nodes:
            if n.asset_id not in aids:
                problems.append(f"node {n.node_id} references unknown asset")
        for e in self.edges:
            if e.asset_id not in aids:
                problems.append(f"edge {e.edge_id} references unknown asset")
            for endpoint, ref in (("source", e.source_node_id), ("target", e.target_node_id)):
                if ref is not None and ref not in nids:
                    problems.append(f"edge {e.edge_id} {endpoint} node not inventoried")
            # every endpoint must resolve OR be explicitly marked unresolved
            if not e.endpoints_resolved and not (e.source_ref or e.target_ref):
                problems.append(f"edge {e.edge_id} unresolved but carries no explanatory ref")
        for fa in self.field_access:
            if fa.asset_id not in aids:
                problems.append(f"field_access {fa.access_id} references unknown asset")
        return problems

    def as_dicts(self) -> dict[str, list[dict]]:
        return {
            "snapshots": [asdict(x) for x in self.snapshots],
            "assets": [asdict(x) for x in self.assets],
            "nodes": [asdict(x) for x in self.nodes],
            "edges": [asdict(x) for x in self.edges],
            "field_access": [asdict(x) for x in self.field_access],
            "findings": [asdict(x) for x in self.findings],
        }
