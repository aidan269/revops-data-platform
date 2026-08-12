#!/usr/bin/env python3
"""GTM Campaigns custom-object extract — read-only.

Extracts HubSpot custom object 2-63647366 ("GTM Campaigns") and its associations
to contacts and deals into append-only raw tables.

This script issues GET requests only. It never creates, updates, archives, or
deletes a HubSpot record, and it never writes an association. Association edges
are copied exactly as HubSpot reports them; nothing is inferred from UTM, email
clicks, web clicks, or contact membership.

Usage:
  python extract/extract_gtm_campaigns.py          # live, read-only
  python extract/extract_gtm_campaigns.py --dry-run # show scope, make no request

Requires HUBSPOT_PRIVATE_APP_TOKEN with crm.objects.custom.read (plus contacts
and deals read scope for association ids) and DATABASE_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
HS_BASE = "https://api.hubapi.com"

# Confirmed CRM ground truth: the custom object, not the native campaign object.
GTM_OBJECT_TYPE = os.getenv("HUBSPOT_GTM_CAMPAIGN_OBJECT_TYPE", "2-63647366").strip()

# Requested properties. hs_object_id and the name field are the only ones the
# measurement layer depends on; everything returned is preserved in raw_properties.
GTM_PROPS = ["hs_object_id", "hs_createdate", "hs_lastmodifieddate"]
NAME_PROPERTY_CANDIDATES = ("gtm_campaign_name", "name", "hs_name", "campaign_name")

REQUIRED_TABLES = (
    "hubspot_gtm_campaigns",
    "hubspot_gtm_campaign_contacts",
    "hubspot_gtm_campaign_deals",
)


def assert_schema_ready(conn) -> None:
    """Fail before any HubSpot request when the landing tables are missing."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw'"
        )
        present = {row[0] for row in cur.fetchall()}
    missing = sorted(set(REQUIRED_TABLES) - present)
    if missing:
        raise RuntimeError(
            "local migrations are required before extraction; missing raw tables: "
            f"{', '.join(missing)}. Run: .venv/bin/python scripts/run_db_migrations.py"
        )


def resolve_name(properties: dict) -> str | None:
    """Return the campaign label without inventing one."""
    for key in NAME_PROPERTY_CANDIDATES:
        value = (properties.get(key) or "").strip()
        if value:
            return value
    return None


def extract(conn, dry_run: bool = False) -> dict[str, int]:
    import requests

    if dry_run:
        print(f"[dry-run] would GET {HS_BASE}/crm/v3/objects/{GTM_OBJECT_TYPE}")
        print("[dry-run] associations=contacts,deals; method=GET only; no write performed")
        return {"campaigns": 0, "contact_links": 0, "deal_links": 0}

    campaigns = contact_links = deal_links = 0
    after = None
    with conn.cursor() as cur:
        while True:
            params = {
                "limit": "100",
                "properties": ",".join(GTM_PROPS + list(NAME_PROPERTY_CANDIDATES)),
                "associations": "contacts,deals",
                "archived": "false",
            }
            if after:
                params["after"] = after
            r = requests.get(
                f"{HS_BASE}/crm/v3/objects/{GTM_OBJECT_TYPE}",
                headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            page = r.json()

            for obj in page.get("results", []):
                props = obj.get("properties", {}) or {}
                cur.execute(
                    """INSERT INTO raw.hubspot_gtm_campaigns
                       (id, name, created_at, updated_at, archived, raw_properties)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        obj["id"],
                        resolve_name(props),
                        props.get("hs_createdate") or None,
                        props.get("hs_lastmodifieddate") or None,
                        bool(obj.get("archived", False)),
                        json.dumps(props),
                    ),
                )
                campaigns += 1

                associations = obj.get("associations", {}) or {}
                for assoc in associations.get("contacts", {}).get("results", []):
                    if assoc.get("id"):
                        cur.execute(
                            """INSERT INTO raw.hubspot_gtm_campaign_contacts
                               (campaign_id, contact_id) VALUES (%s, %s)""",
                            (obj["id"], assoc["id"]),
                        )
                        contact_links += 1
                for assoc in associations.get("deals", {}).get("results", []):
                    if assoc.get("id"):
                        cur.execute(
                            """INSERT INTO raw.hubspot_gtm_campaign_deals
                               (campaign_id, deal_id) VALUES (%s, %s)""",
                            (obj["id"], assoc["id"]),
                        )
                        deal_links += 1

            after = page.get("paging", {}).get("next", {}).get("after")
            if not after:
                break

    conn.commit()
    return {"campaigns": campaigns, "contact_links": contact_links, "deal_links": deal_links}


def main() -> int:
    parser = argparse.ArgumentParser(description="GTM Campaigns custom object → raw schema")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the request scope and exit without calling HubSpot")
    args = parser.parse_args()

    print(f"Extract mode: READ-ONLY (GET only) | object_type={GTM_OBJECT_TYPE}")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        assert_schema_ready(conn)
        if not args.dry_run and not HUBSPOT_TOKEN:
            raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN is not set in this Terminal window.")
        counts = extract(conn, dry_run=args.dry_run)
    finally:
        conn.close()

    print(f"Extracted: {counts['campaigns']} GTM campaigns")
    print(f"  → raw.hubspot_gtm_campaigns: {counts['campaigns']} rows appended")
    print(f"  → raw.hubspot_gtm_campaign_contacts: {counts['contact_links']} rows appended")
    print(f"  → raw.hubspot_gtm_campaign_deals: {counts['deal_links']} rows appended")
    print("No HubSpot record was created, modified, archived, or deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
