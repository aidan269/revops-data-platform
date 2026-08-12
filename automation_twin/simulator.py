"""LangGraph simulator over the canonical automation model.

Executes normalized automation nodes against a synthetic fixture and reports what
WOULD happen. It never performs an external write: there is no external client in
this module, and the approval interrupt is followed by a terminal safe-stop rather
than an executor.
"""
from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from .model import fixture_hash, stable_id
from .policy import (PROTECTED_FIELDS, normalize_label, validate_sample_values,
                     validate_writer)

WOULD_WRITE, WOULD_SKIP, WOULD_CONFLICT, CANNOT_EVALUATE = (
    "would_write", "would_skip", "would_conflict", "cannot_evaluate")


def _merge(left: list, right: list) -> list:
    return (left or []) + (right or [])


class SimState(TypedDict, total=False):
    simulation_id: str
    asset_id: str
    fixture_name: str
    fixture_hash: str
    record: dict[str, Any]
    current_values: dict[str, Any]
    associations: dict[str, list[str]]
    rules: list[dict]
    resolved_target: str
    traversed: Annotated[list[str], _merge]
    proposed_writes: Annotated[list[dict], _merge]
    blocked_writes: Annotated[list[dict], _merge]
    notifications: Annotated[list[dict], _merge]
    delays: Annotated[list[dict], _merge]
    exceptions: Annotated[list[dict], _merge]
    unresolved: Annotated[list[dict], _merge]
    policy_violations: Annotated[list[dict], _merge]
    approval_state: str
    approval_payload: dict
    result: str
    externally_executed: bool


# ---------------------------------------------------------------------------
def n_trigger(state: SimState) -> SimState:
    rec = state.get("record", {})
    return {"traversed": ["trigger"],
            "fixture_hash": fixture_hash(rec),
            "externally_executed": False}


def n_resolve_target(state: SimState) -> SimState:
    """Resolve exactly one target deal, or stop safely.

    A deterministic linkage must name exactly one deal id, and that id must be
    present among the candidate targets. Zero, multiple, absent or invalid
    linkage all stop safely — a target is never guessed.
    """
    assoc = state.get("associations", {}) or {}
    targets = list(assoc.get("deals", []) or [])
    linkage = (state.get("record", {}) or {}).get("linkage")

    def stop(code, detail, extra=None):
        out = {"traversed": ["resolve_target"],
               "exceptions": [{"code": code, "detail": detail}],
               "result": "stopped_safe"}
        if extra:
            out["policy_violations"] = extra
        return out

    if not targets:
        return stop("NO_TARGET", "no associated deal; routed to exception, no target guessed")

    if linkage is None or linkage == "":
        if len(targets) == 1:
            return {"traversed": ["resolve_target"], "resolved_target": targets[0]}
        return stop("AMBIGUOUS_TARGET",
                    f"{len(targets)} candidate deals and no deterministic linkage",
                    [{"policy_id": "POL-009", "detail": "heuristic selection refused"}])

    # A linkage must be a single, concrete deal id.
    if isinstance(linkage, (list, tuple, set)):
        return stop("INVALID_LINKAGE",
                    f"linkage names {len(linkage)} ids; a deterministic link must name exactly one")
    if not isinstance(linkage, str):
        return stop("INVALID_LINKAGE", f"linkage is {type(linkage).__name__}, expected a single deal id")
    if linkage not in targets:
        return stop("LINKAGE_TARGET_NOT_FOUND",
                    f"linkage names a deal that is not among the {len(targets)} candidate targets")

    return {"traversed": ["resolve_target"], "resolved_target": linkage}


def n_evaluate_writes(state: SimState) -> SimState:
    """Classify each modelled rule as would_write / skip / conflict / cannot_evaluate."""
    proposed, blocked, violations = [], [], []
    current = state.get("current_values", {}) or {}
    asset = state.get("asset_id", "unknown")

    for rule in state.get("rules", []) or []:
        prop = rule.get("property")
        value = rule.get("value")
        overwrite = rule.get("overwrite", "only_if_empty")
        existing = current.get(prop)
        entry = {"asset_id": asset, "property": prop, "old_value": existing,
                 "proposed_value": value, "overwrite_behavior": overwrite}

        if value is None:
            entry["disposition"] = CANNOT_EVALUATE
            entry["reason"] = "source value unavailable in fixture"
            blocked.append(entry)
            continue

        # Precedence: a populated destination under a non-overwriting rule is a
        # no-op, so it is a skip rather than a writer conflict. Only rules that
        # would actually write are tested against the protected-field controls.
        if existing not in (None, "") and overwrite != "replace":
            entry["disposition"] = WOULD_SKIP
            entry["reason"] = "destination populated and rule does not overwrite"
            blocked.append(entry)
            continue

        if normalize_label(prop) in PROTECTED_FIELDS:
            writer = validate_writer(asset, prop)
            values_ok = validate_sample_values(prop, [str(value)])
            if not writer.allowed:
                entry["disposition"] = WOULD_CONFLICT
                entry["reason"] = writer.finding
                blocked.append(entry)
                violations.append({"policy_id": "POL-002", "detail": writer.finding})
                continue
            if not values_ok.allowed:
                entry["disposition"] = WOULD_CONFLICT
                entry["reason"] = values_ok.finding
                blocked.append(entry)
                violations.append({"policy_id": "POL-VENDOR", "detail": values_ok.finding})
                continue

        entry["disposition"] = WOULD_WRITE
        proposed.append(entry)

    return {"traversed": ["evaluate_writes"], "proposed_writes": proposed,
            "blocked_writes": blocked, "policy_violations": violations}


def n_approval_interrupt(state: SimState) -> SimState:
    """Approval boundary. Builds the exact payload; never executes anything."""
    writes = state.get("proposed_writes", []) or []
    if not writes:
        return {"traversed": ["approval_interrupt"], "approval_state": "not_required",
                "result": state.get("result") or "completed"}
    payload = {
        "target_system": "hubspot",
        "asset_id": state.get("asset_id"),
        "records": [state["resolved_target"]] if state.get("resolved_target") else [],
        "fields": [w["property"] for w in writes],
        "old_values": {w["property"]: w["old_value"] for w in writes},
        "proposed_values": {w["property"]: w["proposed_value"] for w in writes},
        "reason": "simulated rule evaluation proposed these writes",
        "rollback": "restore the exact old_values listed; writes only target empty destinations",
        "idempotency_key": stable_id("idem", state.get("simulation_id"), state.get("fixture_hash")),
        "evidence_references": ["AUTOMATION-DIGITAL-TWIN simulation"],
    }
    return {"traversed": ["approval_interrupt"], "approval_state": "PENDING_APPROVAL",
            "approval_payload": payload, "result": state.get("result") or "completed"}


def n_safe_stop(state: SimState) -> SimState:
    """Terminal node. There is deliberately no executor after the approval boundary."""
    return {"traversed": ["safe_stop"], "externally_executed": False,
            "result": state.get("result") or "completed"}


def _route_after_target(state: SimState) -> str:
    return "safe_stop" if state.get("result") == "stopped_safe" else "evaluate_writes"


def build_simulator():
    g = StateGraph(SimState)
    g.add_node("trigger", n_trigger)
    g.add_node("resolve_target", n_resolve_target)
    g.add_node("evaluate_writes", n_evaluate_writes)
    g.add_node("approval_interrupt", n_approval_interrupt)
    g.add_node("safe_stop", n_safe_stop)
    g.add_edge(START, "trigger")
    g.add_edge("trigger", "resolve_target")
    g.add_conditional_edges("resolve_target", _route_after_target,
                            {"evaluate_writes": "evaluate_writes", "safe_stop": "safe_stop"})
    g.add_edge("evaluate_writes", "approval_interrupt")
    g.add_edge("approval_interrupt", "safe_stop")
    g.add_edge("safe_stop", END)
    return g.compile(checkpointer=MemorySaver())


def simulate(fixture: dict, *, simulation_id: str | None = None) -> dict:
    """Run one fixture. Returns final state. Performs no external call of any kind."""
    app = build_simulator()
    sim_id = simulation_id or stable_id("sim", fixture.get("fixture_name"),
                                        fixture_hash(fixture))
    init: SimState = {
        "simulation_id": sim_id,
        "asset_id": fixture.get("asset_id", "unknown"),
        "fixture_name": fixture.get("fixture_name", "unnamed"),
        "record": fixture.get("record", {}),
        "current_values": fixture.get("current_values", {}),
        "associations": fixture.get("associations", {}),
        "rules": fixture.get("rules", []),
        "traversed": [], "proposed_writes": [], "blocked_writes": [],
        "notifications": [], "delays": [], "exceptions": [], "unresolved": [],
        "policy_violations": [], "externally_executed": False,
    }
    cfg = {"configurable": {"thread_id": sim_id}}
    final = app.invoke(init, cfg)
    final["externally_executed"] = False  # invariant, asserted in tests
    return final
