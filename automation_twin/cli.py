"""AUTOMATION-DIGITAL-TWIN CLI. Read-only with respect to every external system.

There is deliberately NO `execute` command in this task.

Commands:
  import-evidence        build the graph from repository/warehouse evidence
  validate-graph         referential integrity + endpoint resolution
  protected-writers      list assets that write protected fields
  unresolved             list unresolved dependencies
  simulate               run a named fixture through the LangGraph simulator
  compare-snapshots      drift between two source snapshot sets
  approval-proposal      render an approval-ready proposal (no execution)
  baseline-coverage      collected / partial / not-collected by system
"""
from __future__ import annotations

import argparse
import json

from .adapters import build_graph
from .fixtures import FIXTURES
from .model import NOT_COLLECTED, PARTIAL, COLLECTED
from .policy import PROTECTED_FIELDS, normalize_label, run_policies
from .provenance_contract import LEAD_DATA_PROVIDER_CONTRACT
from .simulator import simulate

FORBIDDEN_COMMANDS = {"execute", "apply", "push-to-hubspot", "write"}


def cmd_import_evidence(_):
    g = build_graph()
    print(json.dumps({"snapshots": len(g.snapshots), "assets": len(g.assets),
                      "nodes": len(g.nodes), "edges": len(g.edges),
                      "field_access": len(g.field_access)}, indent=2))


def cmd_validate_graph(_):
    g = build_graph()
    problems = g.validate()
    print("VALID" if not problems else "INVALID")
    for p in problems:
        print("  -", p)
    return 0 if not problems else 1


def cmd_protected_writers(_):
    g = build_graph()
    for fa in g.field_access:
        if normalize_label(fa.property_name) in PROTECTED_FIELDS and fa.operation in {"write", "create", "clear"}:
            print(f"{fa.property_name:28s} <- {fa.asset_id:45s} [{fa.basis}/{fa.confidence}]")


def cmd_unresolved(_):
    g = build_graph()
    for s in g.snapshots:
        if s.collection_status == NOT_COLLECTED:
            print(f"NOT_COLLECTED  {s.source_system:10s} {s.source_artifact:34s} {s.not_collected_reason}")
    for e in g.edges:
        if not e.endpoints_resolved:
            print(f"UNRESOLVED_EDGE {e.edge_id}  {e.source_ref} -> {e.target_ref}")


def cmd_simulate(args):
    fx = FIXTURES.get(args.fixture)
    if not fx:
        raise SystemExit(f"unknown fixture; choose from: {', '.join(sorted(FIXTURES))}")
    r = simulate(fx)
    print(json.dumps({"fixture": args.fixture, "result": r["result"],
                      "traversed": r["traversed"],
                      "proposed_writes": r["proposed_writes"],
                      "blocked_writes": r["blocked_writes"],
                      "exceptions": r["exceptions"],
                      "approval_state": r.get("approval_state"),
                      "externally_executed": r["externally_executed"]}, indent=2, default=str))


def cmd_compare_snapshots(_):
    g = build_graph()
    by_system = {}
    for s in g.snapshots:
        by_system.setdefault(s.source_system, []).append(s.source_hash)
    print(json.dumps({k: v for k, v in sorted(by_system.items())}, indent=2))
    print("\nDrift is detected by comparing these hashes against a future run.")


def cmd_approval_proposal(_):
    print(json.dumps(LEAD_DATA_PROVIDER_CONTRACT, indent=2))


def cmd_baseline_coverage(_):
    g = build_graph()
    cov = {}
    for s in g.snapshots:
        c = cov.setdefault(s.source_system, {COLLECTED: 0, PARTIAL: 0, NOT_COLLECTED: 0})
        c[s.collection_status] += 1
    print(json.dumps(cov, indent=2))


def cmd_findings(_):
    g = build_graph()
    for f in run_policies(g):
        print(f"[{f.severity}] {f.policy_id} {f.observation}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="automation-twin", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("import-evidence", cmd_import_evidence), ("validate-graph", cmd_validate_graph),
                     ("protected-writers", cmd_protected_writers), ("unresolved", cmd_unresolved),
                     ("compare-snapshots", cmd_compare_snapshots),
                     ("approval-proposal", cmd_approval_proposal),
                     ("baseline-coverage", cmd_baseline_coverage), ("findings", cmd_findings)):
        sub.add_parser(name).set_defaults(func=fn)
    sp = sub.add_parser("simulate")
    sp.add_argument("fixture")
    sp.set_defaults(func=cmd_simulate)
    args = p.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    raise SystemExit(main())
