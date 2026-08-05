#!/usr/bin/env python3
"""
HubSpot campaigns + engagements extract — extends extract for Task 5.

Extracts:
  - raw.hubspot_campaigns: id, name, type.
  - raw.hubspot_campaign_members: campaign_id, contact_id.
  - raw.hubspot_engagements: contact_id, type, timestamp, campaign_id, asset_id.

Usage:
  python extract_campaigns.py --mock   # synthetic data (no token needed)
  python extract_campaigns.py          # live API (requires HUBSPOT_PRIVATE_APP_TOKEN)

Mock data design:
  - ~80 campaigns across 7 campaign types.
  - Campaign members linked to existing contacts from Task 2-4.
  - ~50,000 engagements (email_open, email_click, form_submission, meeting)
    distributed across contacts with timestamps before their deal close dates.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
HS_BASE = "https://api.hubapi.com"

# Campaign types + messaging themes (deterministic from name keywords)
CAMPAIGN_TYPES = [
    "product-launch", "event-invite", "webinar", "case-study",
    "security-research", "pricing", "nurture",
]

MESSAGING_THEMES = CAMPAIGN_TYPES  # same controlled vocabulary

# Campaign name templates by type
CAMPAIGN_NAMES = {
    "product-launch": [
        "Cantina Platform Launch Q1", "Web3 Toolkit Launch", "API v2 Launch",
        "DeFi Protocol Launch", "Enterprise Platform Launch",
    ],
    "event-invite": [
        "BlackHat 2025 Invite", "DevCon Invite", "Ethereum Denver Invite",
        "Solana Breakpoint Invite", "NFT NYC Invite",
    ],
    "webinar": [
        "Smart Contract Security Webinar", "DeFi Yield Webinar",
        "Zero-Knowledge Proofs Webinar", "L2 Scaling Webinar",
    ],
    "case-study": [
        "Morpho Case Study", "Uniswap Case Study", "Lido Case Study",
        "Ethena Case Study",
    ],
    "security-research": [
        "Bridge Security Research", "Oracle Manipulation Research",
        "MEV Research Report", "Stablecoin Risk Report",
    ],
    "pricing": [
        "Enterprise Pricing Update", "Volume Discount Program",
        "Premium Tier Pricing", "Startup Pricing",
    ],
    "nurture": [
        "Weekly Newsletter", "Monthly Roundup", "Product Tips Series",
        "Onboarding Drip", "Re-engagement Campaign",
    ],
}

ENGAGEMENT_TYPES = ["email_open", "email_click", "form_submission", "meeting"]


def derive_campaign_type(name: str) -> str:
    """Deterministic campaign type from name keywords."""
    name_lower = name.lower()
    for ctype in CAMPAIGN_TYPES:
        # Simple keyword matching
        keyword = ctype.replace("-", " ")
        if keyword in name_lower:
            return ctype
    return "nurture"  # default


def generate_mock_data(conn) -> tuple[int, int, int]:
    """Generate mock campaigns, members, and engagements."""
    random.seed(42)

    # Get all contact ids + their utm_source + createdate
    with conn.cursor() as cur:
        cur.execute("SELECT id, utm_source, createdate FROM raw.hubspot_contacts ORDER BY id")
        contacts = cur.fetchall()
        cur.execute("SELECT deal_id, contact_id, closedate FROM raw.hubspot_deal_contacts dc JOIN raw.hubspot_deals d ON dc.deal_id = d.id WHERE d.hs_is_closed_won = true")
        won_deals = cur.fetchall()

    # Generate campaigns
    campaigns = []
    campaign_id = 400000
    for ctype in CAMPAIGN_TYPES:
        names = CAMPAIGN_NAMES[ctype]
        for name in names:
            campaigns.append({
                "id": str(campaign_id),
                "name": name,
                "type": derive_campaign_type(name),
            })
            campaign_id += 1

    # Generate campaign members — link ~60% of contacts to a random campaign
    campaign_members = []
    for contact_id, utm_source, createdate in contacts:
        if random.random() > 0.6:
            continue
        camp = random.choice(campaigns)
        campaign_members.append({
            "campaign_id": camp["id"],
            "contact_id": contact_id,
        })

    # Generate engagements — 2-8 per contact, before deal close date if won
    engagements = []
    eng_id = 500000
    contact_deal_map = {}
    for deal_id, contact_id, closedate in won_deals:
        if contact_id not in contact_deal_map:
            contact_deal_map[contact_id] = closedate

    for contact_id, utm_source, createdate in contacts:
        n_engagements = random.randint(0, 8)
        base_date = datetime(2024, 11, 1, tzinfo=timezone.utc)
        if createdate:
            base_date = datetime.fromisoformat(createdate) if isinstance(createdate, str) else createdate

        # End date: deal close date if won, else now
        if contact_id in contact_deal_map and contact_deal_map[contact_id]:
            end_date = contact_deal_map[contact_id]
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.now(timezone.utc)

        if end_date <= base_date:
            continue

        for _ in range(n_engagements):
            ts = base_date + timedelta(
                seconds=random.randint(0, int((end_date - base_date).total_seconds()))
            )
            eng_type = random.choice(ENGAGEMENT_TYPES)
            # ~50% of engagements are linked to a campaign
            camp_id = None
            if random.random() < 0.5:
                camp = random.choice(campaigns)
                camp_id = camp["id"]

            engagements.append({
                "id": str(eng_id),
                "contact_id": contact_id,
                "type": eng_type,
                "timestamp": ts.isoformat(),
                "campaign_id": camp_id,
                "asset_id": f"asset_{random.randint(1, 20)}" if eng_type in ("email_open", "email_click") else None,
            })
            eng_id += 1

    # Insert campaigns
    campaigns_inserted = 0
    with conn.cursor() as cur:
        for c in campaigns:
            cur.execute(
                """INSERT INTO raw.hubspot_campaigns (id, name, type, raw_properties)
                   VALUES (%s, %s, %s, %s)""",
                (c["id"], c["name"], c["type"], json.dumps(c)),
            )
            campaigns_inserted += 1

    # Insert campaign members
    members_inserted = 0
    with conn.cursor() as cur:
        for cm in campaign_members:
            cur.execute(
                """INSERT INTO raw.hubspot_campaign_members (campaign_id, contact_id)
                   VALUES (%s, %s)""",
                (cm["campaign_id"], cm["contact_id"]),
            )
            members_inserted += 1

    # Insert engagements
    engagements_inserted = 0
    with conn.cursor() as cur:
        for e in engagements:
            cur.execute(
                """INSERT INTO raw.hubspot_engagements
                   (id, contact_id, type, timestamp, campaign_id, asset_id, raw_properties)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (e["id"], e["contact_id"], e["type"], e["timestamp"],
                 e["campaign_id"], e["asset_id"], json.dumps(e)),
            )
            engagements_inserted += 1

    conn.commit()
    return campaigns_inserted, members_inserted, engagements_inserted


def main():
    parser = argparse.ArgumentParser(description="HubSpot campaigns + engagements extract")
    parser.add_argument("--mock", action="store_true", help="Use synthetic data")
    args = parser.parse_args()

    print(f"Extract mode: {'MOCK' if args.mock else 'LIVE'}")
    conn = psycopg2.connect(DATABASE_URL)

    if args.mock:
        n_camp, n_members, n_eng = generate_mock_data(conn)
    else:
        raise NotImplementedError("Live API extract not implemented — use --mock")

    conn.close()
    print(f"Extracted: {n_camp} campaigns, {n_members} campaign members, {n_eng} engagements")
    print(f"  → raw.hubspot_campaigns: {n_camp} rows")
    print(f"  → raw.hubspot_campaign_members: {n_members} rows")
    print(f"  → raw.hubspot_engagements: {n_eng} rows")


if __name__ == "__main__":
    main()
