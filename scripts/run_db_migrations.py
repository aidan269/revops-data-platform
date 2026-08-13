#!/usr/bin/env python3
"""Apply ordered local warehouse migrations safely and idempotently."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
# docker-compose.yml provisions POSTGRES_DB=warehouse with role "revops".
# The default therefore names the database "warehouse", not the role.
DEFAULT_DATABASE_URL = "postgresql://revops:revops@localhost:5432/warehouse"
MIGRATIONS = (
    "03_hubspot_deals.sql",
    "04_hubspot_campaigns.sql",
    "05_deal_source_migration.sql",
    "06_original_traffic_source.sql",
    "07_gtm_campaigns.sql",
    "08_brand_inbound_recovery.sql",
    "09_brand_inbound_grants.sql",
    "10_automation_digital_twin.sql",
    "11_automation_twin_grants.sql",
    "12_automation_twin_refresh.sql",
)
LOCK_ID = 714005


def migration_plan(root: Path = ROOT) -> list[tuple[str, Path, str]]:
    plan = []
    for name in MIGRATIONS:
        path = root / "db" / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        plan.append((name, path, digest))
    return plan


def apply_migrations(database_url: str, root: Path = ROOT) -> None:
    plan = migration_plan(root)
    print(f"[migrate] database={database_url.rsplit('@', 1)[-1]}")
    print(f"[migrate] order={','.join(name for name, _, _ in plan)}")
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_ID,))
            cur.execute("CREATE SCHEMA IF NOT EXISTS analytics")
            cur.execute(
                """CREATE TABLE IF NOT EXISTS analytics.schema_migrations (
                       migration_name TEXT PRIMARY KEY,
                       checksum TEXT NOT NULL,
                       applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
                   )"""
            )
            for name, path, checksum in plan:
                cur.execute(
                    "SELECT checksum FROM analytics.schema_migrations WHERE migration_name = %s",
                    (name,),
                )
                row = cur.fetchone()
                if row:
                    if row[0] != checksum:
                        raise RuntimeError(
                            f"migration checksum drift for {name}: recorded={row[0]} current={checksum}"
                        )
                    print(f"[migrate] skip {name} (already applied, checksum verified)")
                    continue
                print(f"[migrate] apply {name}")
                cur.execute(path.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO analytics.schema_migrations (migration_name, checksum) VALUES (%s, %s)",
                    (name, checksum),
                )
                print(f"[migrate] applied {name}")
    print("[migrate] complete")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="PostgreSQL URL; defaults to DATABASE_URL or the local warehouse database",
    )
    args = parser.parse_args()
    apply_migrations(args.database_url)


if __name__ == "__main__":
    main()
