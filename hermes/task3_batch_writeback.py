#!/usr/bin/env python3
"""
Task 3 Part A — Batch selection, dry-run, and approval artifact.

Steps:
  A1. Select the batch: contacts from mart_enrichment_gaps where hs_seniority
      is null, jobtitle is present, and the deterministic title→seniority
      mapping returns a HIGH-CONFIDENCE EXACT MATCH. Cap at N=25.
      Exclude anything that only resolves via the Ollama fuzzy path.
  A2. Build the change set as dry-run first: write_fields(dry_run=True).
  A3. Export the batch preview CSV and STOP for human approval.

Usage:
  python task3_batch_writeback.py --dry-run         # build preview + CSV
  python task3_batch_writeback.py --live             # go live (requires approval + token)
  python task3_batch_writeback.py --rollback BATCH_ID  # show rollback command
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "writeback"))

import psycopg2
from hubspot_writer import write_fields, rollback_batch, WHITELIST

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")

# ── High-confidence title → seniority mapping ──────────────────────────────
# EXACT match only — no fuzzy, no LLM. These are unambiguous titles where the
# seniority is self-evident from the title itself.
# Format: (lowercase_title_substring, seniority_value, rule_description)

EXACT_MAPPINGS = [
    # Executive C-suite
    ("ceo",              "executive", "exact: 'ceo' → executive"),
    ("cto",              "executive", "exact: 'cto' → executive"),
    ("cfo",              "executive", "exact: 'cfo' → executive"),
    ("coo",              "executive", "exact: 'coo' → executive"),
    ("chief executive",  "executive", "exact: 'chief executive' → executive"),
    ("chief technology", "executive", "exact: 'chief technology' → executive"),
    ("chief financial",  "executive", "exact: 'chief financial' → executive"),
    ("chief operating",  "executive", "exact: 'chief operating' → executive"),
    ("founder",          "executive", "exact: 'founder' → executive"),
    ("owner",            "executive", "exact: 'owner' → executive"),
    # VP
    ("vp of",            "vp",        "exact: 'vp of' → vp"),
    ("vice president",   "vp",        "exact: 'vice president' → vp"),
    # Director / Head of
    ("director",         "director",  "exact: 'director' → director"),
    ("head of",          "director",  "exact: 'head of' → director"),
    # Manager / Lead
    ("manager",          "manager",   "exact: 'manager' → manager"),
    ("lead",             "manager",   "exact: 'lead' → manager"),
    # Senior
    ("senior",            "senior",   "exact: 'senior' → senior"),
    ("sr.",              "senior",   "exact: 'sr.' → senior"),
    ("sr ",               "senior",   "exact: 'sr ' → senior"),
    # Staff / Principal
    ("staff",            "senior",   "exact: 'staff' → senior (staff-level)"),
    ("principal",        "senior",   "exact: 'principal' → senior (principal-level)"),
    # Entry / Junior
    ("junior",           "entry",    "exact: 'junior' → entry"),
    ("analyst",          "entry",    "exact: 'analyst' → entry"),
    ("intern",           "entry",    "exact: 'intern' → entry"),
]

BATCH_LIMIT = 25


def derive_seniority_exact(jobtitle: str) -> tuple[str | None, str | None]:
    """
    High-confidence exact-match mapping. Returns (seniority, rule) or (None, None).
    Uses word-boundary regex to avoid substring false positives (e.g. 'cto' in 'director').
    Only returns a match if the title contains an exact keyword — no fuzzy, no LLM.
    """
    if not jobtitle:
        return None, None
    title_lower = jobtitle.lower().strip()

    for pattern, seniority, rule in EXACT_MAPPINGS:
        # Use word boundary matching to avoid false positives like 'cto' in 'director'
        if re.search(r'\b' + re.escape(pattern) + r'\b', title_lower):
            return seniority, rule

    return None, None  # No exact match → excluded (would go to LLM)


def select_batch(conn) -> list[dict]:
    """Select contacts from mart_enrichment_gaps with exact-match seniority."""
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT contact_id, email, jobtitle, hs_seniority,
                   industry, hs_employee_range
            FROM analytics_analytics.mart_enrichment_gaps
            WHERE (hs_seniority IS NULL OR hs_seniority = '')
              AND jobtitle IS NOT NULL AND jobtitle != ''
            ORDER BY contact_id
        """)
        rows = cur.fetchall()

    batch = []
    for contact_id, email, jobtitle, current_sen, industry, emp_range in rows:
        seniority, rule = derive_seniority_exact(jobtitle)
        if seniority is None:
            continue  # No exact match — excluded (fuzzy/LLM path)
        batch.append({
            "contact_id": contact_id,
            "email": email,
            "jobtitle": jobtitle,
            "old_seniority": current_sen or "",
            "new_seniority": seniority,
            "rule": rule,
            "confidence": "exact",
        })
        if len(batch) >= BATCH_LIMIT:
            break

    return batch


def run_dry_run(conn, batch: list[dict], batch_id: str) -> list[dict]:
    """Build the change set as dry-run first."""
    results = []
    for item in batch:
        result = write_fields(
            "contact",
            item["contact_id"],
            {"hs_seniority": item["new_seniority"]},
            dry_run=True,
            source=f"{item['rule']} | jobtitle='{item['jobtitle']}'",
            batch_id=batch_id,
        )
        results.append(result)
    return results


def export_csv(batch: list[dict], path: str):
    """Export the batch preview CSV for human approval."""
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "contact_id", "email", "jobtitle",
            "old_seniority", "new_seniority", "rule", "confidence"
        ])
        for item in batch:
            writer.writerow([
                item["contact_id"], item["email"], item["jobtitle"],
                item["old_seniority"], item["new_seniority"],
                item["rule"], item["confidence"]
            ])


def run_live(conn, batch: list[dict], batch_id: str) -> dict:
    """Go live: re-read each contact, skip if no longer null, write idempotently."""
    written = []
    skipped = []
    failed = []

    for item in batch:
        try:
            result = write_fields(
                "contact",
                item["contact_id"],
                {"hs_seniority": item["new_seniority"]},
                dry_run=False,
                source=f"{item['rule']} | jobtitle='{item['jobtitle']}'",
                batch_id=batch_id,
            )
            if result["applied"]:
                written.append(result)
            if result["skipped"]:
                skipped.append(result)
        except Exception as e:
            failed.append({
                "contact_id": item["contact_id"],
                "error": str(e),
            })

    return {
        "batch_id": batch_id,
        "total": len(batch),
        "written": len(written),
        "skipped": len(skipped),
        "failed": len(failed),
        "details": {"written": written, "skipped": skipped, "failed": failed},
    }


def verify_live(conn, batch: list[dict], batch_id: str) -> list[dict]:
    """Read the batch back from HubSpot; confirm hs_seniority is set and matches."""
    # In mock mode (no token), we verify from the log instead
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
    results = []

    if not token:
        # No token — verify from the writeback log
        with conn, conn.cursor() as cur:
            cur.execute("""
                SELECT object_id, field, new_value, dry_run
                FROM analytics.hubspot_writeback_log
                WHERE batch_id = %s AND dry_run = false
                ORDER BY id
            """, (batch_id,))
            log_rows = cur.fetchall()

        for obj_id, field, new_val, dry in log_rows:
            results.append({
                "contact_id": obj_id,
                "field": field,
                "verified_value": new_val,
                "source": "analytics.hubspot_writeback_log (no HubSpot token to read back)",
            })
    else:
        # Read back from HubSpot
        for item in batch:
            try:
                old = write_fields.__wrapped__ if False else None  # just use _current_value
                from hubspot_writer import _current_value
                current = _current_value("contact", item["contact_id"], "hs_seniority")
                results.append({
                    "contact_id": item["contact_id"],
                    "expected": item["new_seniority"],
                    "actual": current,
                    "match": current == item["new_seniority"],
                })
            except Exception as e:
                results.append({
                    "contact_id": item["contact_id"],
                    "error": str(e),
                })

    return results


def main():
    parser = argparse.ArgumentParser(description="Task 3 batch writeback")
    parser.add_argument("--dry-run", action="store_true", help="Build preview + CSV (default)")
    parser.add_argument("--live", action="store_true", help="Go live (requires token + approval)")
    parser.add_argument("--rollback", type=str, help="Show rollback command for a batch_id")
    parser.add_argument("--batch-id", type=str, help="Use a specific batch_id")
    args = parser.parse_args()

    if args.rollback:
        calls = rollback_batch(args.rollback)
        print(f"\nRollback for batch {args.rollback}: {len(calls)} reverts")
        print("Command to execute (DO NOT run automatically):")
        print(f"  python task3_batch_writeback.py --live --batch-id {args.rollback}-rollback")
        print("\nReverts:")
        for c in calls:
            print(f"  {c['object_type']} {c['object_id']}  {c['field']}: {c['old']} → {c['new']}")
        return

    batch_id = args.batch_id or f"task3-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"

    conn = psycopg2.connect(DATABASE_URL)

    # ── A1: Select the batch ───────────────────────────────────────────────
    print("=" * 60)
    print("  TASK 3 — PART A: LIVE WRITEBACK BATCH")
    print("=" * 60)

    batch = select_batch(conn)
    print(f"\nA1. Batch selected: {len(batch)} contacts (cap={BATCH_LIMIT})")
    print(f"    Batch ID: {batch_id}")
    print(f"    Selection: hs_seniority IS NULL AND jobtitle present AND exact-match mapping")
    print(f"    Excluded: anything requiring Ollama fuzzy path")
    print()

    if not batch:
        print("No contacts matched. Exiting.")
        return

    for item in batch:
        print(f"  {item['contact_id']:>6}  {item['email']:<25}  '{item['jobtitle']}' → '{item['new_seniority']}'  [{item['rule']}]")

    if args.live:
        # ── A4-A7: Go live ─────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  A4. LIVE WRITE (dry_run=False)")
        print("=" * 60)
        print(f"  Token: {os.getenv('HUBSPOT_PRIVATE_APP_TOKEN', 'NOT SET')[:20]}...")
        print(f"  Batch ID: {batch_id}")

        result = run_live(conn, batch, batch_id)
        print(f"\n  Written: {result['written']}")
        print(f"  Skipped: {result['skipped']}")
        print(f"  Failed:  {result['failed']}")

        if result["failed"]:
            print("\n  FAILED:")
            for f in result["details"]["failed"]:
                print(f"    {f['contact_id']}: {f['error']}")

        if result["skipped"]:
            print("\n  SKIPPED (clobber guard — value was set since preview):")
            for s in result["details"]["skipped"]:
                print(f"    {s['object_id']}: {s['skipped']}")

        # ── A6: Verify ─────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  A6. VERIFY (read back from HubSpot)")
        print("=" * 60)
        verifications = verify_live(conn, batch, batch_id)
        for v in verifications:
            if "error" in v:
                print(f"  {v['contact_id']}: ERROR — {v['error']}")
            elif "match" in v:
                status = "✓" if v["match"] else "✗ MISMATCH"
                print(f"  {v['contact_id']}: expected='{v['expected']}' actual='{v['actual']}' {status}")
            else:
                print(f"  {v['contact_id']}: {v['field']}='{v['verified_value']}' ({v['source']})")

        # ── A7: Show rollback command ──────────────────────────────────────
        print("\n" + "=" * 60)
        print("  A7. ROLLBACK COMMAND (do not execute)")
        print("=" * 60)
        calls = rollback_batch(batch_id)
        print(f"\n  To revert batch {batch_id} ({len(calls)} writes):")
        print(f"  python task3_batch_writeback.py --rollback {batch_id}")
        print(f"\n  Reverts:")
        for c in calls:
            print(f"    {c['object_type']} {c['object_id']}  {c['field']}: '{c['old']}' → '{c['new']}'")

    else:
        # ── A2: Build dry-run change set ──────────────────────────────────
        print("\n" + "=" * 60)
        print("  A2. DRY-RUN CHANGE SET")
        print("=" * 60)
        print(f"  Batch ID: {batch_id}")

        results = run_dry_run(conn, batch, batch_id)
        written_count = sum(1 for r in results if r["applied"])
        print(f"\n  Dry-run writes logged: {written_count}")
        for r in results:
            for a in r["applied"]:
                print(f"  {r['object_id']:>6}  {a['field']}: '{a['old']}' → '{a['new']}'  [{r.get('batch_id', batch_id)}]")

        # ── A3: Export CSV + STOP ─────────────────────────────────────────
        csv_path = os.path.join(os.path.dirname(__file__), "..", "hermes", "out", "task3_batch_preview.csv")
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        export_csv(batch, csv_path)

        print("\n" + "=" * 60)
        print("  A3. APPROVAL ARTIFACT")
        print("=" * 60)
        print(f"\n  CSV exported: {csv_path}")
        print(f"  Batch ID: {batch_id}")
        print(f"  Total contacts in batch: {len(batch)}")
        print(f"\n  ⏸ STOPPING FOR HUMAN APPROVAL.")
        print(f"  Review the CSV above. To go live, run:")
        print(f"  python task3_batch_writeback.py --live --batch-id {batch_id}")
        print(f"\n  Do not proceed without an explicit 'approved' from a human.")

    conn.close()


if __name__ == "__main__":
    main()
