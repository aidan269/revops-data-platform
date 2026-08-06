#!/bin/sh
# run_long_job.sh — run long jobs under `caffeinate -s` so macOS stays awake
# for the whole run (prevents sleep from stalling dbt builds, extracts, and
# docker compose operations mid-flight).
#
# Usage:
#   scripts/run_long_job.sh <command> [args...]
#
# Examples:
#   scripts/run_long_job.sh dbt build --profiles-dir transform
#   scripts/run_long_job.sh python extract/extract_hubspot.py --mock
#   scripts/run_long_job.sh docker compose --profile monitor run --rm monitor

set -eu

if [ $# -eq 0 ]; then
  echo "usage: $0 <command> [args...]" >&2
  exit 64
fi

exec caffeinate -s "$@"
