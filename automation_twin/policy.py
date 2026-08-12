"""Policy-as-code for the automation digital twin.

Two responsibilities:
  1. Protected-field guardrails (import mappings, writer registry).
  2. Graph-level control checks that emit Findings.

Nothing here contacts an external system.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Finding, Graph, NOT_COLLECTED, stable_id

# ---------------------------------------------------------------------------
# Protected fields. Writing these without an approved writer is a control failure.
# ---------------------------------------------------------------------------
PROTECTED_FIELDS: dict[str, str] = {
    "primary_campaign_source": "campaign attribution",
    "latest_campaign_source": "campaign attribution",
    "deal_source": "deal attribution",
    "repo_uri": "canonical deal repository",
}

# Known enrichment/provenance vendor literals observed in the estate.
VENDOR_LITERALS = {
    "apollo", "findymail", "leadmagic", "prospeo", "icypeas",
    "user managed", "clay", "nooks", "read ai", "make", "zoominfo", "lusha",
}

# Generic column names that carry provenance, never campaign attribution.
PROVENANCE_COLUMN_TOKENS = {
    "vendor", "provider", "enriched_by", "enrichedby", "data_source", "datasource",
    "source_file", "sourcefile", "tool", "provenance", "supplied_by", "suppliedby",
    "email_source", "emailsource", "lead_source_tool", "enrichment_source",
    "found_by", "foundby", "list_source", "import_file", "filename",
}

FILE_EXTENSION_RE = re.compile(r"\.(csv|xlsx|xls|tsv|json)$", re.I)

# Registry: which assets may write which protected fields. Deliberately starts
# with NO Apollo asset approved to write Primary Campaign Source.
APPROVED_PROTECTED_WRITERS: dict[str, set[str]] = {
    "primary_campaign_source": {"hubspot:workflow:1833911074"},
    "latest_campaign_source": set(),
    "deal_source": set(),
    "repo_uri": set(),
}


def normalize_label(label: str) -> str:
    """Lowercase, collapse separators. Normalisation only — never fuzzy approval."""
    return re.sub(r"[\s_\-]+", "_", (label or "").strip().lower()).strip("_")


@dataclass
class MappingVerdict:
    allowed: bool
    reason: str
    finding: str | None = None

    def __bool__(self) -> bool:  # pragma: no cover - convenience
        return self.allowed


def validate_import_mapping(source_column: str, destination_field: str) -> MappingVerdict:
    """Fix 1 — reject vendor/provenance columns mapped to protected attribution fields.

    Fails CLOSED: anything ambiguous is rejected, never approved by resemblance.
    """
    dest = normalize_label(destination_field)
    src = normalize_label(source_column)

    if dest not in PROTECTED_FIELDS:
        return MappingVerdict(True, f"'{destination_field}' is not a protected field")

    if not src:
        return MappingVerdict(
            False, "empty or unnamed source column mapped to a protected field",
            f"AMBIGUOUS MAPPING REJECTED: unnamed column -> {destination_field}",
        )

    src_tokens = set(src.split("_"))
    if src in PROVENANCE_COLUMN_TOKENS or (src_tokens & PROVENANCE_COLUMN_TOKENS):
        return MappingVerdict(
            False, "provenance column mapped to a protected attribution field",
            f"BLOCKED: provenance column '{source_column}' -> protected "
            f"'{destination_field}'. Route provenance to Lead Data Provider instead.",
        )

    if src.replace("_", " ") in VENDOR_LITERALS or src in VENDOR_LITERALS:
        return MappingVerdict(
            False, "vendor literal used as a column name for a protected field",
            f"BLOCKED: vendor column '{source_column}' -> protected '{destination_field}'.",
        )

    if FILE_EXTENSION_RE.search(source_column or ""):
        return MappingVerdict(
            False, "filename-like column mapped to a protected field",
            f"BLOCKED: filename column '{source_column}' -> protected '{destination_field}'.",
        )

    return MappingVerdict(
        False, "unrecognised column mapped to a protected field; failing closed",
        f"BLOCKED (fail-closed): '{source_column}' -> protected '{destination_field}' "
        f"is not an approved mapping. Approve explicitly if intended.",
    )


def validate_sample_values(destination_field: str, values: list[str]) -> MappingVerdict:
    """Reject a mapping whose sample values are vendor literals, whatever the column name."""
    dest = normalize_label(destination_field)
    if dest not in PROTECTED_FIELDS:
        return MappingVerdict(True, "destination not protected")
    hits = sorted({v for v in values if normalize_label(v).replace("_", " ") in VENDOR_LITERALS})
    if hits:
        return MappingVerdict(
            False, "vendor literals present in sample values",
            f"BLOCKED: values {hits} are enrichment vendors, not campaigns "
            f"(destination '{destination_field}').",
        )
    return MappingVerdict(True, "no vendor literals in sample")


def validate_writer(asset_key: str, destination_field: str) -> MappingVerdict:
    """Fix 3 — only registered assets may write a protected field."""
    dest = normalize_label(destination_field)
    if dest not in PROTECTED_FIELDS:
        return MappingVerdict(True, "destination not protected")
    approved = APPROVED_PROTECTED_WRITERS.get(dest, set())
    if asset_key in approved:
        return MappingVerdict(True, f"{asset_key} is a registered writer for {dest}")
    return MappingVerdict(
        False, "unregistered writer for a protected field",
        f"BLOCKED: '{asset_key}' is not a registered writer of '{destination_field}'.",
    )


def assert_no_production_adapter() -> None:
    """Structural guarantee: no production write adapter exists in this package.

    Raises if one is ever added without an execution manifest.
    """
    import importlib
    for candidate in ("automation_twin.executor", "automation_twin.production_adapter"):
        try:
            importlib.import_module(candidate)
        except ModuleNotFoundError:
            continue
        raise AssertionError(
            f"{candidate} exists; a production write adapter must not be importable "
            "without an approved execution manifest"
        )


# ---------------------------------------------------------------------------
# Graph-level control checks
# ---------------------------------------------------------------------------
def _f(policy_id, severity, observation, inference, *, asset_id=None, system=None,
       object_type=None, prop=None, evidence=None, recurrence=None,
       reversibility=None, remediation=None) -> Finding:
    return Finding(
        finding_id=stable_id("finding", policy_id, asset_id, prop, observation[:60]),
        policy_id=policy_id, severity=severity, asset_id=asset_id, system=system,
        object_type=object_type, property_name=prop, observation=observation,
        inference=inference, evidence_reference=evidence, recurrence_risk=recurrence,
        reversibility=reversibility, proposed_remediation=remediation,
    )


def run_policies(graph: Graph) -> list[Finding]:
    """Evaluate control policies over the graph. Observation and inference stay separate."""
    out: list[Finding] = []
    assets = {a.asset_id: a for a in graph.assets}

    # POL-001 multiple active writers to the same protected field
    writers: dict[tuple, list[str]] = {}
    for fa in graph.field_access:
        if fa.operation in {"write", "create", "clear"}:
            writers.setdefault((fa.system, fa.object_type, fa.property_name), []).append(fa.asset_id)
    for (system, obj, prop), owners in writers.items():
        active = [o for o in set(owners) if assets.get(o) and assets[o].state == "active"]
        if len(active) > 1:
            out.append(_f("POL-001", "P1",
                f"{len(active)} active assets write {system}.{obj}.{prop}: {sorted(active)}",
                "Concurrent writers can overwrite one another; last-writer-wins is not determinable from evidence.",
                system=system, object_type=obj, prop=prop))

    # POL-002 unknown/unregistered writer to a protected field
    for (system, obj, prop), owners in writers.items():
        if normalize_label(prop) in PROTECTED_FIELDS:
            for owner in sorted(set(owners)):
                verdict = validate_writer(owner, prop)
                if not verdict.allowed:
                    a = assets.get(owner)
                    out.append(_f("POL-002", "P1",
                        f"Asset '{owner}' writes protected field {prop} and is not in the writer registry.",
                        "Unregistered writers to attribution fields are how vendor values reach campaign attribution.",
                        asset_id=owner, system=system, object_type=obj, prop=prop,
                        evidence=(a.raw_definition_ref if a else None),
                        remediation="Register the writer explicitly or remove its write access."))

    # POL-003 active automation with an unresolved target
    for e in graph.edges:
        if not e.endpoints_resolved:
            a = assets.get(e.asset_id)
            if a and a.state in {"active", "unknown"}:
                out.append(_f("POL-003", "P2",
                    f"Edge {e.edge_id} on {a.state} asset '{a.name or a.asset_id}' has an unresolved endpoint "
                    f"(source_ref={e.source_ref}, target_ref={e.target_ref}).",
                    "An unresolved target cannot be simulated or verified; it is not evidence of breakage.",
                    asset_id=e.asset_id, evidence=e.evidence_reference))

    # POL-004 evidence source unavailable but represented as healthy
    for s in graph.snapshots:
        if s.collection_status == NOT_COLLECTED and s.baseline_established:
            out.append(_f("POL-004", "P1",
                f"Snapshot {s.snapshot_id} for {s.source_system} is NOT_COLLECTED yet claims a baseline.",
                "This would present an inaccessible surface as healthy.", system=s.source_system))

    # POL-005 legacy authentication identity
    for a in graph.assets:
        owner = (a.owner_identity or "")
        if owner.endswith("@spearbit.com"):
            out.append(_f("POL-005", "P2",
                f"Asset '{a.name or a.asset_id}' ({a.source_system}) is owned by legacy identity {owner}.",
                "Deprovisioning a legacy identity could break owned assets or an integration authentication.",
                asset_id=a.asset_id, system=a.source_system,
                reversibility="reversible by reassignment",
                remediation="Enumerate all users, then reassign before retiring the identity."))

    # POL-006 notification routed to an inactive/unknown owner
    for n in graph.nodes:
        if n.node_type == "notify" and n.config.get("recipient_state") in {"inactive", "unknown"}:
            out.append(_f("POL-006", "P2",
                f"Notify node {n.node_id} targets a {n.config.get('recipient_state')} recipient.",
                "Notifications to deactivated users fail silently and leave work unrouted.",
                asset_id=n.asset_id))

    # POL-007 external action with no error path
    with_error = {e.asset_id for e in graph.edges if e.path_type in {"failure", "fallback", "timeout"}}
    for a in graph.assets:
        has_ext = any(n.asset_id == a.asset_id and n.external_side_effect != "none" for n in graph.nodes)
        if has_ext and a.asset_id not in with_error and a.evidence_state != NOT_COLLECTED:
            out.append(_f("POL-007", "P3",
                f"Asset '{a.name or a.asset_id}' performs an external side effect with no modelled error path.",
                "Absence of a modelled error path may reflect incomplete collection rather than a real gap.",
                asset_id=a.asset_id))

    # POL-008 creation without duplicate protection
    for n in graph.nodes:
        if n.node_type == "create" and not n.config.get("duplicate_protection"):
            out.append(_f("POL-008", "P2",
                f"Create node {n.node_id} has no duplicate protection configured.",
                "Repeat triggers could produce duplicate records.", asset_id=n.asset_id,
                remediation="Add a duplicate guard keyed on the originating request."))

    # POL-009 association chosen heuristically rather than deterministically
    for n in graph.nodes:
        if n.node_type == "associate" and n.config.get("selection") == "heuristic":
            out.append(_f("POL-009", "P1",
                f"Associate node {n.node_id} selects its target heuristically.",
                "A heuristic target choice can attach data to the wrong record; deterministic linkage is required.",
                asset_id=n.asset_id,
                remediation="Require a deterministic link or route to an exception queue."))

    # POL-010 default / unreviewed synchronisation settings
    for a in graph.assets:
        if a.asset_type == "integration" and (a.raw_definition_ref or "").find("default_settings") >= 0:
            out.append(_f("POL-010", "P2",
                f"Integration '{a.name}' reports default or unreviewed synchronisation settings.",
                "Default enrichment settings are a recurrence risk but their content was not collectable.",
                asset_id=a.asset_id, system=a.source_system, recurrence="unknown until reviewed"))

    # POL-011 active sequence with no verified owner
    for a in graph.assets:
        if a.asset_type == "sequence" and a.state == "active" and not a.owner_identity:
            out.append(_f("POL-011", "P2",
                f"Active sequence '{a.name}' has no verified owner.", None, asset_id=a.asset_id))

    return out
