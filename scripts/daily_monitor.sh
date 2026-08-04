#!/bin/sh
# Daily data-quality monitor — runs via docker compose service or cron.
# Posts anomalies to Slack (if SLACK_WEBHOOK_URL is set), prints to stdout otherwise.
# Surface only — never auto-fix.

set -e

cd /app

echo "=== RevOps DQ Monitor — $(date -u '+%Y-%m-%d %H:%M UTC') ==="

# Run the monitor (dbt tests + freshness + volume deltas + Apollo check + UTM corruption)
# In the container, DATABASE_URL points to the postgres service
python scripts/dq_monitor.py

echo "=== Monitor run complete ==="
