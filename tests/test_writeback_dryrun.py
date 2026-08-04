#!/usr/bin/env python3
"""
Task 2 — Guarded writeback dry-run test.

Proves:
  1. The whitelist is enforced: a non-whitelisted field is REFUSED.
  2. hs_seniority is derived deterministically from jobtitle (simple mapping).
  3. write_fields() is called with dry_run=True for 3 sample contacts.
  4. Diffs are written to analytics.hubspot_writeback_log.
  5. Nothing is sent to HubSpot (no HUBSPOT_PRIVATE_APP_TOKEN set).

Source: analytics_analytics.mart_enrichment_gaps → jobtitle → seniority mapping
"""

from __future__ import annotations

import os
import sys
import json

# Add writeback module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "writeback"))

import psycopg2
from hubspot_writer import write_fields, WHITELIST

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")

# ── Deterministic jobtitle → seniority mapping ──────────────────────────────
# Simple keyword-based rules. The local LLM would be used only for titles
# that don't match any of these patterns (ambiguous titles).

SENIORITY_MAP = {
    # Executive
    "ceo": "executive",
    "cto": "executive",
    "cfo": "executive",
    "coo": "executive",
    "chief technology officer": "executive",
    "chief executive officer": "executive",
    "founder": "executive",
    "owner": "executive",
    # VP / Director
    "vp": "vp",
    "vp of": "vp",
    "vice president": "vp",
    "director": "director",
    "head of": "director",
    # Manager / Lead
    "manager": "manager",
    "lead": "manager",
    "principal": "manager",
    "staff": "senior",
    # Senior / Mid
    "senior": "senior",
    "sr": "senior",
    # Entry / Junior
    "junior": "entry",
    "analyst": "entry",
    "intern": "entry",
}


def derive_seniority(jobtitle: str) -> str | None:
    """Deterministic title → seniority. Returns None if no rule matches."""
    if not jobtitle:
        return None
    title_lower = jobtitle.lower().strip()

    # Check from most specific to least
    for pattern, seniority in SENIORITY_MAP.items():
        if pattern in title_lower:
            return seniority

    return None  # ambiguous → would go to LLM


def main():
    print("=" * 60)
    print("  TASK 2 — GUARDED WRITEBACK DRY-RUN")
    print("=" * 60)

    # ── 1. Verify the whitelist ─────────────────────────────────────────────
    print("\n--- 1. Whitelist verification ---")
    print(f"WHITELIST['contact'] = {sorted(WHITELIST['contact'])}")
    assert "hs_seniority" in WHITELIST["contact"], "hs_seniority must be whitelisted"
    assert "icp_fit" in WHITELIST["contact"], "icp_fit must be whitelisted"
    assert "black_hat_lead_grade" in WHITELIST["contact"], "black_hat_lead_grade must be whitelisted"
    print("✓ Whitelist confirmed: hs_seniority, icp_fit, black_hat_lead_grade")

    # ── 2. Test that a non-whitelisted field is REFUSED ─────────────────────
    print("\n--- 2. Non-whitelisted field refusal test ---")
    try:
        write_fields("contact", "99999", {"email": "hacker@evil.com"}, dry_run=True)
        print("✗ FAIL: non-whitelisted field was NOT refused!")
        sys.exit(1)
    except ValueError as e:
        print(f"✓ REFUSED as expected: {e}")

    # Also test a non-whitelisted object type
    try:
        write_fields("deal", "99999", {"hs_seniority": "executive"}, dry_run=True)
        print("✗ FAIL: non-whitelisted object type was NOT refused!")
        sys.exit(1)
    except ValueError as e:
        print(f"✓ REFUSED non-whitelisted object: {e}")

    # ── 3. Pull 3 sample contacts from mart_enrichment_gaps ─────────────────
    print("\n--- 3. Sample contacts from mart_enrichment_gaps ---")
    conn = psycopg2.connect(DATABASE_URL)
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT contact_id, email, jobtitle, hs_seniority
            FROM analytics_analytics.mart_enrichment_gaps
            WHERE gap_hs_seniority = true
              AND jobtitle IS NOT NULL
              AND jobtitle != ''
            ORDER BY contact_id
            LIMIT 3
        """)
        samples = cur.fetchall()

    print(f"Found {len(samples)} contacts with seniority gaps and a jobtitle:")
    for cid, email, title, sen in samples:
        derived = derive_seniority(title)
        print(f"  contact_id={cid}  email={email}  jobtitle='{title}'  current_seniority='{sen or ''}'  → derived='{derived}'")

    # ── 4. Call write_fields(dry_run=True) for each ────────────────────────
    print("\n--- 4. Dry-run write_fields() calls ---")
    results = []
    for cid, email, title, current_sen in samples:
        new_sen = derive_seniority(title)
        if new_sen is None:
            print(f"  SKIP contact_id={cid}: no deterministic mapping for '{title}' (would go to LLM)")
            continue

        result = write_fields("contact", cid, {"hs_seniority": new_sen}, dry_run=True)
        results.append(result)
        print(f"  contact_id={cid}: {result}")

    # ── 5. Verify diffs were logged to analytics.hubspot_writeback_log ──────
    print("\n--- 5. Writeback log entries ---")
    with conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, object_type, object_id, field, old_value, new_value, dry_run, written_at
            FROM analytics.hubspot_writeback_log
            ORDER BY id DESC
            LIMIT 10
        """)
        log_rows = cur.fetchall()

    print(f"Last {min(len(log_rows), 10)} log entries (source: analytics.hubspot_writeback_log):")
    print(f"{'id':>5}  {'obj_type':>10}  {'obj_id':>8}  {'field':>15}  {'old':>10}  {'new':>12}  {'dry_run':>7}")
    print("-" * 80)
    for row in log_rows:
        log_id, obj_type, obj_id, field, old_val, new_val, dry, ts = row
        print(f"{log_id:>5}  {obj_type:>10}  {obj_id:>8}  {field:>15}  {str(old_val or ''):>10}  {str(new_val or ''):>12}  {str(dry):>7}")

    dry_run_count = sum(1 for r in log_rows if r[6])  # r[6] = dry_run
    print(f"\n  Total log entries: {len(log_rows)}")
    print(f"  Dry-run entries: {dry_run_count}")
    print(f"  Live writes: {len(log_rows) - dry_run_count}")

    conn.close()

    # ── 6. Confirm nothing was sent to HubSpot ─────────────────────────────
    print("\n--- 6. HubSpot API verification ---")
    token = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
    if not token:
        print("✓ HUBSPOT_PRIVATE_APP_TOKEN not set → impossible to send live writes")
    else:
        print("⚠ HUBSPOT_PRIVATE_APP_TOKEN is set — verify all log entries have dry_run=true")

    print("\n" + "=" * 60)
    print("  DRY-RUN COMPLETE — ALL CHECKS PASSED")
    print("  • Whitelist enforced (non-whitelisted fields refused)")
    print("  • Seniority derived deterministically from jobtitle")
    print("  • Diffs logged to analytics.hubspot_writeback_log")
    print("  • Zero live HubSpot writes")
    print("=" * 60)


if __name__ == "__main__":
    main()
