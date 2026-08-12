#!/usr/bin/env python3
"""Load the automation digital twin graph into the local warehouse. Idempotent.

Local Postgres only. Performs no external call of any kind.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import hashlib
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from automation_twin.adapters import build_graph, collection_run_id  # noqa: E402
from automation_twin.policy import run_policies             # noqa: E402
from automation_twin.fixtures import FIXTURES               # noqa: E402
from automation_twin.simulator import simulate              # noqa: E402
from automation_twin.model import stable_id                 # noqa: E402

TABLES = ("automation_findings", "automation_runs", "automation_field_access",
          "automation_edges", "automation_nodes", "automation_assets",
          "automation_source_snapshots")


def _content_hash(row: dict) -> str:
    return hashlib.sha256(
        json.dumps(row, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def upsert(cur, table, rows, key, load_id, jsonb=()):
    """Refresh-safe upsert.

    ON CONFLICT DO UPDATE, never DO NOTHING: an entity seen again has its mutable
    columns and last_seen_load refreshed, so a corrected observation is not frozen
    behind its first write. first_seen_load is preserved.
    """
    inserted = updated = 0
    for r in rows:
        payload = dict(r)
        payload["content_hash"] = _content_hash(r)
        payload["first_seen_load"] = load_id
        payload["last_seen_load"] = load_id
        payload["last_refreshed_at"] = datetime.now(timezone.utc)
        cols = list(payload)
        vals = [Json(payload[c]) if c in jsonb else payload[c] for c in cols]
        updatable = [c for c in cols if c not in (key, "first_seen_load")]
        setters = ", ".join(f"{c} = EXCLUDED.{c}" for c in updatable)
        cur.execute(
            f"INSERT INTO raw.{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))}) "
            f"ON CONFLICT ({key}) DO UPDATE SET {setters} "
            f"RETURNING (xmax = 0) AS was_insert", vals)
        if cur.fetchone()[0]:
            inserted += 1
        else:
            updated += 1
    return {"inserted": inserted, "refreshed": updated}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    args = ap.parse_args()
    if not args.database_url:
        raise SystemExit("--database-url or DATABASE_URL required")

    g = build_graph()
    problems = g.validate()
    if problems:
        raise SystemExit("[load] graph invalid:\n  - " + "\n  - ".join(problems))
    findings = run_policies(g)

    runs = []
    for name, fx in FIXTURES.items():
        r = simulate(fx)
        assert r["externally_executed"] is False
        runs.append(dict(
            run_id=stable_id("run", name, r["fixture_hash"]),
            asset_id=fx["asset_id"] if fx["asset_id"] in g.asset_ids() else None,
            run_kind="simulation", fixture_name=name,
            input_fixture_hash=r["fixture_hash"],
            result="stopped_safe" if r["result"] == "stopped_safe" else "completed",
            traversed_nodes=r["traversed"], proposed_writes=r["proposed_writes"],
            blocked_writes=r["blocked_writes"],
            findings=r["policy_violations"] + r["exceptions"],
            ledger_reference="AUTOMATION-DIGITAL-TWIN", executed_externally=False))

    d = g.as_dicts()
    counts = {}
    with psycopg2.connect(args.database_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", (714010,))
        run_id = collection_run_id([s["source_artifact"] for s in d["snapshots"]])
        graph_hash = _content_hash(d)
        cur.execute(
            "INSERT INTO raw.automation_loads (collection_run_id, graph_content_hash, source_count, notes) "
            "VALUES (%s, %s, %s, %s) RETURNING load_id",
            (run_id, graph_hash, len(d["snapshots"]), "automation_twin loader"))
        load_id = cur.fetchone()[0]
        counts["snapshots"] = upsert(cur, "automation_source_snapshots", d["snapshots"], "snapshot_id", load_id)
        counts["assets"] = upsert(cur, "automation_assets", d["assets"], "asset_id", load_id)
        counts["nodes"] = upsert(cur, "automation_nodes", d["nodes"], "node_id", load_id, jsonb=("config",))
        counts["edges"] = upsert(cur, "automation_edges", d["edges"], "edge_id", load_id)
        counts["field_access"] = upsert(cur, "automation_field_access", d["field_access"], "access_id", load_id)
        counts["findings"] = upsert(cur, "automation_findings",
                                    [asdict(f) for f in findings], "finding_id", load_id)
        counts["runs"] = upsert(cur, "automation_runs", runs, "run_id", load_id,
                                jsonb=("traversed_nodes", "proposed_writes",
                                       "blocked_writes", "findings"))
        totals = {}
        for t in TABLES:
            cur.execute(f"SELECT count(*) FROM raw.{t}")
            totals[t] = cur.fetchone()[0]
    print("[load] inserted:", json.dumps(counts))
    print("[load] totals:  ", json.dumps(totals))
    print("[load] complete — no external system was contacted")


if __name__ == "__main__":
    main()
