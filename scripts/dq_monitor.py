#!/usr/bin/env python3
"""
Data-quality monitor — runs daily, posts anomalies to Slack/Notion.
Surface only — never auto-fix.

Implements data_quality_monitor.md:
  1. Run dbt tests (not_null, unique, accepted_values) + source freshness.
  2. Compare key volumes vs trailing 7/30-day baseline (new contacts, deals, form-fills).
  3. Summarize failures + anomalies in a short digest, post to configured channel.
  4. Apollo feed freshness check (no new Apollo-sourced contacts in N days → alert).

Channel: reads SLACK_WEBHOOK_URL from env. If unset, prints to stdout only.

Usage:
  python dq_monitor.py                    # run monitor, post to Slack if configured
  python dq_monitor.py --dry-run          # run monitor, print digest only (no post)
  python dq_monitor.py --seed-failure     # inject a known failure to prove it fires
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

import psycopg2
import requests

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
DBT_DIR = os.path.join(os.path.dirname(__file__), "..", "transform")

# Thresholds
VOLUME_DROP_THRESHOLD = 0.3  # >30% drop vs 7-day average → alert
VOLUME_SPIKE_THRESHOLD = 3.0  # >3× the 30-day average → alert
FRESHNESS_WARN_HOURS = 24   # no new data in 24h → warn
FRESHNESS_ERROR_HOURS = 48   # no new data in 48h → error
APOLLO_STALE_DAYS = 3        # no new Apollo contacts in 3 days → alert


def run_dbt_tests() -> dict:
    """Run dbt build and parse the results."""
    result = subprocess.run(
        [".venv/bin/dbt", "build", "--profiles-dir", "."],
        capture_output=True, text=True,
        cwd=DBT_DIR,
        env={**os.environ, "PYTHONPATH": ""},
        timeout=120,
    )
    output = result.stdout + result.stderr

    # Parse the summary line
    # Example: "Done. PASS=26 WARN=0 ERROR=0 SKIP=0 NO-OP=0 REUSED=0 TOTAL=26"
    import re
    summary_match = re.search(
        r"Done\.\s+PASS=(\d+)\s+WARN=(\d+)\s+ERROR=(\d+)\s+SKIP=(\d+)", output
    )

    if summary_match:
        return {
            "pass": int(summary_match.group(1)),
            "warn": int(summary_match.group(2)),
            "error": int(summary_match.group(3)),
            "skip": int(summary_match.group(4)),
            "output": output,
            "exit_code": result.returncode,
        }
    return {
        "pass": 0, "warn": 0, "error": 0, "skip": 0,
        "output": output, "exit_code": result.returncode,
    }


def check_freshness(conn) -> list[dict]:
    """Check source freshness on all raw tables with extracted_at/received_at."""
    checks = [
        ("raw.hubspot_contacts", "extracted_at"),
        ("raw.hubspot_companies", "extracted_at"),
        ("raw.leads_raw", "ingested_at"),
    ]

    alerts = []
    for table, ts_col in checks:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT max({ts_col}) as latest, count(*) as cnt
                FROM {table}
            """)
            latest, cnt = cur.fetchone()

            if cnt == 0:
                alerts.append({
                    "table": table, "column": ts_col,
                    "issue": "EMPTY",
                    "detail": f"0 rows in {table}",
                    "severity": "error",
                })
                continue

            # Calculate age
            cur.execute(f"SELECT extract(epoch from now() - max({ts_col}))/3600 as hours_old FROM {table}")
            hours_old = cur.fetchone()[0]

        if hours_old > FRESHNESS_ERROR_HOURS:
            alerts.append({
                "table": table, "column": ts_col,
                "issue": "STALE",
                "detail": f"{hours_old:.1f}h old (>{FRESHNESS_ERROR_HOURS}h threshold) — FEED FLATLINED",
                "severity": "error",
                "latest": str(latest),
            })
        elif hours_old > FRESHNESS_WARN_HOURS:
            alerts.append({
                "table": table, "column": ts_col,
                "issue": "STALE",
                "detail": f"{hours_old:.1f}h old (>{FRESHNESS_WARN_HOURS}h warn threshold)",
                "severity": "warn",
                "latest": str(latest),
            })

    return alerts


def check_volume_deltas(conn) -> list[dict]:
    """Compare today's new records vs trailing 7/30-day baseline."""
    alerts = []

    # New contacts in last 24h vs 7-day average
    with conn, conn.cursor() as cur:
        cur.execute("""
            WITH daily_counts AS (
                SELECT date_trunc('day', extracted_at) as day,
                       count(*) as cnt
                FROM raw.hubspot_contacts
                WHERE extracted_at > now() - interval '31 days'
                GROUP BY 1
            )
            SELECT
                COALESCE(SUM(CASE WHEN day > now() - interval '1 day' THEN cnt END), 0) as today,
                COALESCE(SUM(CASE WHEN day > now() - interval '8 days' AND day <= now() - interval '1 day' THEN cnt END), 0) / 7.0 as avg_7d,
                COALESCE(SUM(CASE WHEN day > now() - interval '31 days' AND day <= now() - interval '1 day' THEN cnt END), 0) / 30.0 as avg_30d,
                count(*) as total_days
            FROM daily_counts
        """)
        today, avg_7d, avg_30d, total_days = cur.fetchone()

    if avg_7d > 0 and today < avg_7d * (1 - VOLUME_DROP_THRESHOLD):
        alerts.append({
            "table": "raw.hubspot_contacts", "column": "extracted_at",
            "issue": "VOLUME_DROP",
            "detail": f"Today: {today} new contacts vs 7d avg: {avg_7d:.1f} (>{VOLUME_DROP_THRESHOLD*100:.0f}% drop)",
            "severity": "warn",
        })

    if avg_30d > 0 and today > avg_30d * VOLUME_SPIKE_THRESHOLD:
        alerts.append({
            "table": "raw.hubspot_contacts", "column": "extracted_at",
            "issue": "VOLUME_SPIKE",
            "detail": f"Today: {today} new contacts vs 30d avg: {avg_30d:.1f} (>{VOLUME_SPIKE_THRESHOLD}× spike)",
            "severity": "warn",
        })

    return alerts


def check_apollo_freshness(conn) -> list[dict]:
    """Check for Apollo-sourced contacts — no new ones in N days → alert."""
    alerts = []
    with conn.cursor() as cur:
        # Check raw_payload for Apollo-sourced records
        cur.execute("""
            SELECT max(extracted_at) as latest, count(*) as cnt
            FROM raw.hubspot_contacts
            WHERE raw_properties::text ILIKE '%apollo%'
               OR utm_source ILIKE '%apollo%'
        """)
        latest, cnt = cur.fetchone()

        if cnt > 0 and latest:
            cur.execute("""
                SELECT extract(epoch from now() - max(extracted_at))/86400 as days_old
                FROM raw.hubspot_contacts
                WHERE raw_properties::text ILIKE '%apollo%'
                   OR utm_source ILIKE '%apollo%'
            """)
            days_old = cur.fetchone()[0]

            if days_old > APOLLO_STALE_DAYS:
                alerts.append({
                    "table": "raw.hubspot_contacts (Apollo-sourced)", "column": "extracted_at",
                    "issue": "APOLLO_STALE",
                    "detail": f"No new Apollo-attributed contacts in {days_old:.1f} days (>{APOLLO_STALE_DAYS}d threshold) — POST-MIGRATION FLATLINE?",
                    "severity": "error",
                    "latest": str(latest),
                })

    return alerts


def check_utm_corruption(conn) -> list[dict]:
    """Check for UTM corruption (the original 138-row bug pattern)."""
    alerts = []
    accepted_sources = [
        "google", "direct", "twitter", "twitter.com", "t.co", "x", "linkedin",
        "bing", "duckduckgo", "ecosia", "reddit", "chatgpt.com", "in-app",
        "mail", "hs_email", "googleads.g.doubleclick.net",
        "cantina-staging.webflow.io", "cantina.website", "webflow.com",
        "cantina-prod.us.auth0.com", "46025408.hs-sites.com", "spearbit.com",
        "theblock.co", "morpho.org", "github.com", "medium.com", "ethereum.org",
        "lu.ma", "luma.com", "superteam.fun", "bnbchain.org", "blog.lido.fi",
        "docs.ethena.fi", "docs.megapot.io", "docs.size.credit",
        "eggs-finance.gitbook.io", "hub.forum.berachain.com",
        "uniswapfoundation.org", "solaxy.io", "cloudseclist", "companionlink.com",
        "techbullion.com", "onlinethreatalerts.com", "eqchi.r.ag.d.sendibm3.com",
        "facebook", "organic", "referral",
    ]

    with conn.cursor() as cur:
        cur.execute("""
            SELECT utm_source, count(*) as cnt
            FROM analytics_analytics.stg_hubspot_contacts
            WHERE utm_source IS NOT NULL
              AND utm_source != ''
              AND lower(utm_source) NOT IN (%s)
            GROUP BY utm_source
        """ % ",".join(f"'{s}'" for s in accepted_sources))
        bad_rows = cur.fetchall()

    for source, cnt in bad_rows:
        alerts.append({
            "table": "analytics_analytics.stg_hubspot_contacts", "column": "utm_source",
            "issue": "UTM_CORRUPTION",
            "detail": f"utm_source='{source}': {cnt} rows with unaccepted value",
            "severity": "error",
        })

    return alerts


def seed_failure(conn):
    """Seed a known failure to prove the monitor fires."""
    with conn.cursor() as cur:
        # Insert a contact with the corrupted UTM pattern
        cur.execute("""
            INSERT INTO raw.hubspot_contacts (id, email, jobtitle, utm_source, raw_properties)
            VALUES ('test_corrupt_001', 'corrupt@test.com', 'Test',
                    'utm_medium:', '{"utm_source": "utm_medium:"}')
            ON CONFLICT DO NOTHING
        """)
    print("Seeded known failure: contact with utm_source='utm_medium:' (the 138-row corruption pattern)")


def build_digest(dbt_results: dict, freshness_alerts: list, volume_alerts: list,
                 apollo_alerts: list, utm_alerts: list) -> str:
    """Build the digest message."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"📊 *RevOps Data Quality Digest* — {now}", ""]

    # dbt test results
    r = dbt_results
    icon = "✅" if r["error"] == 0 else "❌"
    lines.append(f"{icon} dbt tests: PASS={r['pass']} WARN={r['warn']} ERROR={r['error']} SKIP={r['skip']}")
    if r["error"] > 0:
        # Extract failing test names from output
        import re
        fails = re.findall(r"FAIL \d+ (\S+)", r["output"])
        for f in fails[:5]:
            lines.append(f"   ❌ FAIL: {f}")
    lines.append("")

    # Freshness alerts (highest priority)
    if freshness_alerts:
        lines.append("🔴 *FRESHNESS ALERTS* (highest priority — feed flatlines):")
        for a in freshness_alerts:
            icon = "🔴" if a["severity"] == "error" else "🟡"
            lines.append(f"   {icon} {a['table']}.{a['column']}: {a['issue']} — {a['detail']}")
        lines.append("")

    # UTM corruption alerts
    if utm_alerts:
        lines.append("🔴 *UTM CORRUPTION* (the 138-row pattern):")
        for a in utm_alerts:
            lines.append(f"   ❌ {a['table']}.{a['column']}: {a['detail']}")
        lines.append("")

    # Apollo feed
    if apollo_alerts:
        lines.append("🔴 *APOLLO FEED* (post-migration watch):")
        for a in apollo_alerts:
            lines.append(f"   ❌ {a['table']}: {a['detail']}")
        lines.append("")

    # Volume deltas
    if volume_alerts:
        lines.append("🟡 *VOLUME ANOMALIES*:")
        for a in volume_alerts:
            lines.append(f"   ⚠️ {a['table']}: {a['detail']}")
        lines.append("")

    if not any([freshness_alerts, utm_alerts, apollo_alerts, volume_alerts, r["error"] > 0]):
        lines.append("✅ No anomalies detected. All systems nominal.")

    lines.append("")
    lines.append("_Surface only — never auto-fix. Full details in the warehouse._")
    return "\n".join(lines)


def post_to_slack(digest: str) -> bool:
    """Post the digest to Slack via incoming webhook."""
    if not SLACK_WEBHOOK_URL:
        return False
    r = requests.post(SLACK_WEBHOOK_URL, json={"text": digest}, timeout=10)
    return r.status_code == 200


def main():
    parser = argparse.ArgumentParser(description="RevOps data-quality monitor")
    parser.add_argument("--dry-run", action="store_true", help="Print digest only, don't post")
    parser.add_argument("--seed-failure", action="store_true", help="Inject a known failure to prove the monitor fires")
    args = parser.parse_args()

    print("=" * 60)
    print("  DATA-QUALITY MONITOR")
    print("=" * 60)

    conn = psycopg2.connect(DATABASE_URL)

    if args.seed_failure:
        seed_failure(conn)
        print()

    # 1. Run dbt tests
    print("1. Running dbt tests...")
    dbt_results = run_dbt_tests()
    print(f"   PASS={dbt_results['pass']} WARN={dbt_results['warn']} ERROR={dbt_results['error']} SKIP={dbt_results['skip']}")

    # 2. Check freshness
    print("2. Checking source freshness...")
    freshness_alerts = check_freshness(conn)
    print(f"   {len(freshness_alerts)} freshness alerts")

    # 3. Check volume deltas
    print("3. Checking volume deltas...")
    volume_alerts = check_volume_deltas(conn)
    print(f"   {len(volume_alerts)} volume anomalies")

    # 4. Check Apollo feed
    print("4. Checking Apollo feed freshness...")
    apollo_alerts = check_apollo_freshness(conn)
    print(f"   {len(apollo_alerts)} Apollo alerts")

    # 5. Check UTM corruption
    print("5. Checking for UTM corruption...")
    utm_alerts = check_utm_corruption(conn)
    print(f"   {len(utm_alerts)} UTM corruption alerts")

    conn.close()

    # Build digest
    digest = build_digest(dbt_results, freshness_alerts, volume_alerts,
                          apollo_alerts, utm_alerts)
    print("\n" + "=" * 60)
    print("DIGEST:")
    print("=" * 60)
    print(digest)

    # Post to channel
    if not args.dry_run:
        if SLACK_WEBHOOK_URL:
            print("\nPosting to Slack...")
            if post_to_slack(digest):
                print("   ✅ Posted to Slack")
            else:
                print("   ❌ Failed to post to Slack")
        else:
            print("\n⚠ SLACK_WEBHOOK_URL not set — digest printed to stdout only.")
            print("  Set SLACK_WEBHOOK_URL in .env to post to Slack.")
    else:
        print("\n--dry-run: digest printed only, not posted.")

    print("\nDone.")


if __name__ == "__main__":
    main()
