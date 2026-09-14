#!/usr/bin/env python3
"""
HubSpot deals extract — extends extract_hubspot.py for Task 4.

Extracts:
  - raw.hubspot_deals: core deal fields plus nullable CRM-admin readiness
    fields (owner, next step/date, product/service, billing model).
  - raw.hubspot_deal_contacts: deal_id, contact_id associations.

Usage:
  python extract_deals.py --mock          # synthetic data (no token needed)
  python extract_deals.py                 # live API (requires HUBSPOT_PRIVATE_APP_TOKEN)

Mock data design:
  - 138 contacts with corrupted UTM (utm_source='utm_medium:') — regression guard.
  - ~1,885 total deals with hs_is_closed_won=true — regression guard.
  - Deals distributed across channels per the funnel taxonomy.
  - Deal-contact associations link deals back to the contacts from Task 2/3.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/warehouse")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
HS_BASE = "https://api.hubapi.com"

DEAL_FIELD_PROPERTIES = {
    "deal_owner_id": os.getenv("HUBSPOT_DEAL_OWNER_PROPERTY", "hubspot_owner_id").strip(),
    "next_step": os.getenv("HUBSPOT_DEAL_NEXT_STEP_PROPERTY", "hs_next_step").strip(),
    "next_step_updated_at": os.getenv("HUBSPOT_DEAL_NEXT_STEP_DATE_PROPERTY", "").strip(),
    "product_service": os.getenv("HUBSPOT_DEAL_PRODUCT_SERVICE_PROPERTY", "").strip(),
    "billing_model": os.getenv("HUBSPOT_DEAL_BILLING_MODEL_PROPERTY", "").strip(),
}

CORE_DEAL_PROPS = [
    "amount", "dealstage", "pipeline", "hs_is_closed_won",
    "createdate", "closedate", "deal_source",
    # CRM-010: native HubSpot Original Traffic Source. Confirmed internal name,
    # so it is requested unconditionally rather than via an env-configured
    # mapping. Preserved as evidence only; it never sets Deal Source.
    "hs_analytics_source",
]

REQUIRED_DEAL_COLUMNS = {
    "deal_source", "deal_owner_id", "next_step", "next_step_updated_at",
    "product_service", "billing_model", "original_traffic_source",
    "raw_properties",
}


def assert_live_schema_ready(conn) -> None:
    """Fail before any HubSpot request when the local deal schema is stale."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT column_name
               FROM information_schema.columns
               WHERE table_schema = 'raw' AND table_name = 'hubspot_deals'"""
        )
        present = {row[0] for row in cur.fetchall()}
    missing = sorted(REQUIRED_DEAL_COLUMNS - present)
    if missing:
        raise RuntimeError(
            "local database migrations are required before live extraction; "
            f"missing raw.hubspot_deals columns: {', '.join(missing)}. "
            "Run: .venv/bin/python scripts/run_db_migrations.py"
        )


def requested_deal_properties() -> list[str]:
    """Return configured HubSpot internal property names without empty values."""
    return list(dict.fromkeys(CORE_DEAL_PROPS + [
        value for value in DEAL_FIELD_PROPERTIES.values() if value
    ]))


def canonicalize_crm_admin_fields(properties: dict) -> dict:
    """Preserve source nulls while adding stable canonical keys to raw JSON."""
    canonical = dict(properties)
    canonical["_crm_admin_fields_extracted"] = True
    for canonical_name, source_name in DEAL_FIELD_PROPERTIES.items():
        canonical[f"_crm_admin_{canonical_name}"] = (
            properties.get(source_name) or None if source_name else None
        )
    return canonical

# ── Mock data generation ────────────────────────────────────────────────────
# Channel distribution for mock contacts (first-touch UTM source).
# The 12 existing contacts from Task 2/3 get deals, plus we generate enough
# additional contacts+deals to hit the regression guards:
#   - 138 contacts with utm_source='utm_medium:' (corrupted)
#   - ~1,885 total closed-won deals

CHANNELS = [
    # (channel_name, utm_source, weight, win_rate, avg_amount)
    ("Google Ads",         "google",                25, 0.12, 25000),
    ("LinkedIn",           "linkedin",             18, 0.15, 35000),
    ("X / Twitter",        "twitter",              12, 0.08, 18000),
    ("Organic Search",     "bing",                   5, 0.18, 22000),
    ("Community / Social", "reddit",                 8, 0.10, 15000),
    ("Email / In-app",     "hs_email",               7, 0.22, 40000),
    ("Webflow / Cantina",  "cantina.website",        10, 0.14, 28000),
    ("Referral / Partner", "spearbit.com",            8, 0.25, 50000),
    ("Press / Media",      "techbullion.com",         3, 0.06, 12000),
    ("Direct",             "direct",                  4, 0.20, 30000),
]

# The corrupted UTM bucket — 138 contacts, low win rate (they're bad data)
CORRUPTED_CHANNEL = ("Unknown (corrupted UTM)", "utm_medium:", 138, 0.03, 10000)

TOTAL_WON_TARGET = 1885


def generate_mock_data() -> tuple[list, list, list]:
    """Generate mock deals, deal-contact associations, and additional contacts."""
    random.seed(42)  # deterministic

    # Start with the 12 existing contacts from Task 2/3
    existing_contacts = [
        ("1001", "google", "alice@acme.io"),
        ("1002", "linkedin", "bob@techcorp.com"),
        ("1003", "twitter", "carol@startup.dev"),
        ("1004", "google", "dave@bigfirm.com"),
        ("1005", "referral", "eve@consulting.co"),
        ("1006", "linkedin", "frank@enterprise.com"),
        ("1007", "direct", "grace@smb.io"),
        ("1008", "google", "henry@scaleup.ai"),
        ("1009", "referral", "ivy@nonprofit.org"),
        ("1010", "google", "jack@finventures.com"),
        ("1011", "google", "kate@acme.io"),
        ("1012", "linkedin", "leo@techcorp.com"),
    ]

    # Generate additional contacts to reach the regression guard counts
    all_contacts = list(existing_contacts)
    # Add corrupted UTM contacts (138 total — we already have 0 in existing)
    next_id = 2000
    for i in range(138):
        all_contacts.append((str(next_id + i), "utm_medium:", f"corrupt{i}@test.com"))
    next_id += 138

    # Add clean contacts to have enough volume for ~1885 wins
    # Total contacts needed: ~1885 wins / ~0.13 avg win rate ≈ 14,500
    total_needed = 14500 - len(all_contacts)
    for i in range(total_needed):
        # Pick channel by weight
        channels_weighted = []
        for ch_name, utm, weight, wr, amt in CHANNELS:
            channels_weighted.extend([(ch_name, utm)] * weight)
        ch_name, utm = random.choice(channels_weighted)
        all_contacts.append((str(next_id + i), utm, f"user{next_id + i}@mock.com"))
    next_id += total_needed

    # Generate deals — one per contact (some contacts have no deal)
    deals = []
    deal_contacts = []
    deal_id = 300000
    won_count = 0

    for contact_id, utm_source, email in all_contacts:
        # ~80% of contacts have a deal
        if random.random() > 0.8:
            continue

        # Determine channel + win rate
        if utm_source == "utm_medium:":
            win_rate = CORRUPTED_CHANNEL[3]
            avg_amount = CORRUPTED_CHANNEL[4]
        else:
            channel_info = next((c for c in CHANNELS if c[1] == utm_source), None)
            if channel_info:
                win_rate = channel_info[3]
                avg_amount = channel_info[4]
            else:
                win_rate = 0.10
                avg_amount = 20000

        # Create deal
        is_won = random.random() < win_rate
        amount = int(avg_amount * random.uniform(0.5, 2.0))

        # Dates
        created = datetime(2024, 11, 1, tzinfo=timezone.utc) + timedelta(
            days=random.randint(0, 600),
            hours=random.randint(0, 23)
        )
        closed = None
        if is_won:
            closed = created + timedelta(days=random.randint(7, 180))
            won_count += 1

        deals.append({
            "id": str(deal_id),
            "amount": amount,
            "dealstage": "closedwon" if is_won else ("closedlost" if random.random() < 0.3 else "qualifications"),
            "pipeline": "default",
            "hs_is_closed_won": is_won,
            "createdate": created.isoformat(),
            "closedate": closed.isoformat() if closed else None,
            "deal_source": None,
            "_crm_admin_fields_extracted": True,
            "_crm_admin_deal_owner_id": None,
            "_crm_admin_next_step": None,
            "_crm_admin_next_step_updated_at": None,
            "_crm_admin_product_service": None,
            "_crm_admin_billing_model": None,
        })
        deal_contacts.append({
            "deal_id": str(deal_id),
            "contact_id": contact_id,
        })
        deal_id += 1

    # If we're short of 1885 wins, add more won deals
    while won_count < TOTAL_WON_TARGET:
        contact_id, utm_source, email = random.choice(all_contacts)
        if utm_source == "utm_medium:":
            continue  # corrupted bucket stays low
        created = datetime(2024, 11, 1, tzinfo=timezone.utc) + timedelta(
            days=random.randint(0, 600), hours=random.randint(0, 23)
        )
        closed = created + timedelta(days=random.randint(7, 180))
        channel_info = next((c for c in CHANNELS if c[1] == utm_source), None)
        amt = int((channel_info[4] if channel_info else 20000) * random.uniform(0.5, 2.0))

        deals.append({
            "id": str(deal_id),
            "amount": amt,
            "dealstage": "closedwon",
            "pipeline": "default",
            "hs_is_closed_won": True,
            "createdate": created.isoformat(),
            "closedate": closed.isoformat(),
            "deal_source": None,
            "_crm_admin_fields_extracted": True,
            "_crm_admin_deal_owner_id": None,
            "_crm_admin_next_step": None,
            "_crm_admin_next_step_updated_at": None,
            "_crm_admin_product_service": None,
            "_crm_admin_billing_model": None,
        })
        deal_contacts.append({
            "deal_id": str(deal_id),
            "contact_id": contact_id,
        })
        won_count += 1
        deal_id += 1

    return all_contacts, deals, deal_contacts


def extract_deals_mock(conn) -> tuple[int, int]:
    """Insert synthetic deals + associations."""
    all_contacts, deals, deal_contacts = generate_mock_data()

    # Also insert the additional contacts (beyond the 12 from Task 2/3)
    existing_ids = set()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM raw.hubspot_contacts")
        existing_ids = {r[0] for r in cur.fetchall()}

    contacts_inserted = 0
    with conn.cursor() as cur:
        for contact_id, utm_source, email in all_contacts:
            if contact_id in existing_ids:
                continue
            props = {"email": email, "utm_source": utm_source}
            cur.execute(
                """INSERT INTO raw.hubspot_contacts
                   (id, email, utm_source, raw_properties)
                   VALUES (%s, %s, %s, %s)""",
                (contact_id, email, utm_source, json.dumps(props)),
            )
            contacts_inserted += 1

    deals_inserted = 0
    with conn.cursor() as cur:
        for d in deals:
            cur.execute(
                """INSERT INTO raw.hubspot_deals
                   (id, amount, dealstage, pipeline, hs_is_closed_won,
                    createdate, closedate, deal_source, deal_owner_id, next_step,
                    next_step_updated_at, product_service, billing_model,
                    original_traffic_source, raw_properties)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    d["id"], d["amount"], d["dealstage"], d["pipeline"],
                    d["hs_is_closed_won"], d["createdate"], d["closedate"],
                    d.get("deal_source"),
                    d.get("_crm_admin_deal_owner_id"), d.get("_crm_admin_next_step"),
                    d.get("_crm_admin_next_step_updated_at"), d.get("_crm_admin_product_service"),
                    d.get("_crm_admin_billing_model"),
                    d.get("hs_analytics_source"),
                    json.dumps(d),
                ),
            )
            deals_inserted += 1

    associations_inserted = 0
    with conn.cursor() as cur:
        for dc in deal_contacts:
            cur.execute(
                """INSERT INTO raw.hubspot_deal_contacts
                   (deal_id, contact_id) VALUES (%s, %s)""",
                (dc["deal_id"], dc["contact_id"]),
            )
            associations_inserted += 1

    conn.commit()
    return deals_inserted, associations_inserted


DEAL_COMPANY_DDL = """
CREATE TABLE IF NOT EXISTS raw.hubspot_deal_companies (
    deal_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def extract_deals_live(conn) -> tuple[int, int, int]:
    """Page HubSpot deals API → raw.hubspot_deals (append-only)."""
    import requests

    deals_count = 0
    assoc_count = 0
    company_assoc_count = 0
    after = None
    with conn.cursor() as cur:
        cur.execute(DEAL_COMPANY_DDL)
        while True:
            # Include contact associations in the deal response. The former
            # collection-level /deals/associations/contact endpoint is not a
            # valid HubSpot v3 route.
            params = {
                "limit": "100",
                "properties": ",".join(requested_deal_properties()),
                "associations": "contacts,companies",
            }
            if after:
                params["after"] = after
            r = requests.get(
                f"{HS_BASE}/crm/v3/objects/deals",
                headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
                params=params,
                timeout=30,
            )
            r.raise_for_status()
            page = r.json()

            for obj in page.get("results", []):
                props = obj.get("properties", {})
                canonical_props = canonicalize_crm_admin_fields(props)
                amount_str = props.get("amount")
                amount = float(amount_str) if amount_str else None
                cur.execute(
                    """INSERT INTO raw.hubspot_deals
                       (id, amount, dealstage, pipeline, hs_is_closed_won,
                        createdate, closedate, deal_source, deal_owner_id, next_step,
                        next_step_updated_at, product_service, billing_model,
                        original_traffic_source, raw_properties)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        obj["id"], amount,
                        props.get("dealstage"), props.get("pipeline"),
                        props.get("hs_is_closed_won", "").lower() == "true" if props.get("hs_is_closed_won") else None,
                        # HubSpot returns an empty string for an unset close
                        # date. PostgreSQL timestamps require NULL instead.
                        props.get("createdate") or None,
                        props.get("closedate") or None,
                        props.get("deal_source") or None,
                        canonical_props.get("_crm_admin_deal_owner_id"),
                        canonical_props.get("_crm_admin_next_step"),
                        canonical_props.get("_crm_admin_next_step_updated_at"),
                        canonical_props.get("_crm_admin_product_service"),
                        canonical_props.get("_crm_admin_billing_model"),
                        props.get("hs_analytics_source") or None,
                        json.dumps(canonical_props),
                    ),
                )
                deals_count += 1
                for association in obj.get("associations", {}).get("contacts", {}).get("results", []):
                    contact_id = association.get("id")
                    if contact_id:
                        cur.execute(
                            """INSERT INTO raw.hubspot_deal_contacts
                               (deal_id, contact_id) VALUES (%s, %s)""",
                            (obj["id"], contact_id),
                        )
                        assoc_count += 1
                for association in obj.get("associations", {}).get("companies", {}).get("results", []):
                    company_id = association.get("id")
                    if company_id:
                        cur.execute(
                            """INSERT INTO raw.hubspot_deal_companies
                               (deal_id, company_id) VALUES (%s, %s)""",
                            (obj["id"], company_id),
                        )
                        company_assoc_count += 1
            after = page.get("paging", {}).get("next", {}).get("after")
            if not after:
                break
            time.sleep(0.5)

    conn.commit()
    return deals_count, assoc_count, company_assoc_count


def main():
    parser = argparse.ArgumentParser(description="HubSpot deals extract → raw schema")
    parser.add_argument("--mock", action="store_true", help="Use synthetic data")
    args = parser.parse_args()

    print(f"Extract mode: {'MOCK' if args.mock else 'LIVE'}")
    print(f"DATABASE_URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")

    conn = psycopg2.connect(DATABASE_URL)

    if args.mock:
        n_deals, n_assoc = extract_deals_mock(conn)
        n_company_assoc = 0
    else:
        if not HUBSPOT_TOKEN:
            raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN is not set in this Terminal window.")
        assert_live_schema_ready(conn)
        n_deals, n_assoc, n_company_assoc = extract_deals_live(conn)

    conn.close()
    print(f"Extracted: {n_deals} deals, {n_assoc} deal-contact associations")
    print(f"  → raw.hubspot_deals: {n_deals} rows appended")
    print(f"  → raw.hubspot_deal_contacts: {n_assoc} rows appended")
    print(f"  → raw.hubspot_deal_companies: {n_company_assoc} rows appended")

    # Report regression guard counts
    conn2 = psycopg2.connect(DATABASE_URL)
    with conn2.cursor() as cur:
        cur.execute("SELECT count(*) FROM raw.hubspot_contacts WHERE utm_source = 'utm_medium:'")
        n_corrupt = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FROM raw.hubspot_deals WHERE hs_is_closed_won = true""")
        n_won = cur.fetchone()[0]
    conn2.close()
    print(f"\nRegression guards:")
    print(f"  Corrupted UTM contacts: {n_corrupt} (target: 138)")
    print(f"  Closed-won deals: {n_won} (target: ~1,885)")


if __name__ == "__main__":
    main()
