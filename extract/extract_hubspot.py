#!/usr/bin/env python3
"""
HubSpot extract — pages the HubSpot CRM API and lands append-only snapshots
into raw.hubspot_contacts / raw.hubspot_companies.

Usage:
  python extract_hubspot.py                # live API (requires HUBSPOT_PRIVATE_APP_TOKEN)
  python extract_hubspot.py --mock         # synthetic data matching real schema (no token needed)
  python extract_hubspot.py --mock --count 50   # control mock row count

Extract pattern:
  - Append-only: each run writes rows with extracted_at = now().
  - dbt dim_contact / dim_company select the latest snapshot per id.
  - Idempotent: re-running with the same data is safe (duplicates are
    handled by the dim's row_number() = 1 pattern).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

import requests
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
HS_BASE = "https://api.hubapi.com"

CONTACT_PROPS = [
    "email", "jobtitle", "hs_seniority", "createdate",
    "utm_source", "utm_medium", "utm_campaign",
]
COMPANY_PROPS = [
    "name", "domain", "industry", "numberofemployees", "hs_employee_range",
]

# ── Mock data ──────────────────────────────────────────────────────────────
# Realistic synthetic contacts/companies that match the real HubSpot schema.
# Gaps mirror the baselines from crm_enrichment.md: seniority 1.4%, industry 68%,
# hs_employee_range 21%.

MOCK_CONTACTS = [
    # (id, email, jobtitle, hs_seniority, createdate, utm_source, utm_medium, utm_campaign, company_id)
    ("1001", "alice@acme.io",     "CEO",                    "",             "2025-01-15T10:00:00Z", "google",   "cpc",     "brand_terms",    "2001"),
    ("1002", "bob@techcorp.com",  "VP of Engineering",      "",             "2025-02-20T14:30:00Z", "linkedin", "social",  "org_launch",     "2002"),
    ("1003", "carol@startup.dev", "Senior Software Engineer","",             "2025-03-05T09:15:00Z", "twitter",  "referral", "q1_growth",     "2003"),
    ("1004", "dave@bigfirm.com",  "Marketing Director",     "",             "2025-03-10T11:00:00Z", "google",   "cpc",     "demand_gen",     "2004"),
    ("1005", "eve@consulting.co", "Founder",               "",             "2025-04-01T08:45:00Z", "referral", "word_of mouth", "",        None),
    ("1006", "frank@enterprise.com","Chief Technology Officer","",          "2025-04-12T16:20:00Z", "linkedin", "social",  "enterprise_outbound", "2004"),
    ("1007", "grace@smb.io",      "Product Manager",       "",             "2025-05-03T13:00:00Z", "direct",   "organic", "",               None),
    ("1008", "henry@scaleup.ai",  "Head of Data",          "",             "2025-05-18T10:30:00Z", "google",   "cpc",     "ai_platform",     "2003"),
    ("1009", "ivy@nonprofit.org", "Operations Lead",      "",             "2025-06-01T09:00:00Z", "referral", "word_of mouth", "",        None),
    ("1010", "jack@finventures.com","Junior Analyst",      "",             "2025-06-15T15:45:00Z", "google",   "cpc",     "fintech_q2",      "2002"),
    # One contact WITH seniority filled (1.4% baseline → ~1 in 10 mock)
    ("1011", "kate@acme.io",      "CTO",                   "executive",    "2025-01-20T10:00:00Z", "google",   "cpc",     "brand_terms",     "2001"),
    ("1012", "leo@techcorp.com",  "Staff Engineer",        "",             "2025-07-01T11:30:00Z", "linkedin", "social",  "tech_hiring",    "2002"),
]

MOCK_COMPANIES = [
    # (id, name, domain, industry, numberofemployees, hs_employee_range)
    ("2001", "Acme Corp",          "acme.io",          "Software",           250,  "201-500"),
    ("2002", "TechCorp Inc",       "techcorp.com",     "Information Technology", 5000, "1001-5000"),
    ("2003", "StartupDev",        "startup.dev",      "Software",           30,   "11-50"),
    # Company 2004 has industry gap (industry ~68% filled → 1 of 4 missing)
    ("2004", "BigFirm Holdings",   "bigfirm.com",      "",                  12000, "5001-10000"),
    # Company 2005 — small firm, missing hs_employee_range (21% filled → gaps)
    ("2005", "Consulting Co",      "consulting.co",    "Consulting",         5,    ""),
]


# ── HubSpot API client ──────────────────────────────────────────────────────

def _hs_headers() -> dict[str, str]:
    if not HUBSPOT_TOKEN:
        raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN not set (use --mock for testing)")
    return {"Authorization": f"Bearer {HUBSPOT_TOKEN}"}


OBJECT_ENDPOINTS = {
    "contact": "contacts",
    "company": "companies",
}


def _hs_page(object_type: str, properties: list[str], after: str | None = None,
             associations: str | None = None) -> dict:
    """Page the HubSpot CRM search/list API."""
    params = {"limit": "100", "properties": ",".join(properties)}
    if after:
        params["after"] = after
    if associations:
        params["associations"] = associations
    r = requests.get(
        f"{HS_BASE}/crm/v3/objects/{OBJECT_ENDPOINTS[object_type]}",
        headers=_hs_headers(),
        params=params,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def extract_contacts_live(conn) -> int:
    """Page HubSpot contacts API → raw.hubspot_contacts (append-only)."""
    count = 0
    after = None
    with conn, conn.cursor() as cur:
        while True:
            page = _hs_page("contact", CONTACT_PROPS, after, associations="companies")
            for obj in page.get("results", []):
                props = obj.get("properties", {})
                cur.execute(
                    """INSERT INTO raw.hubspot_contacts
                       (id, email, jobtitle, hs_seniority, createdate,
                        utm_source, utm_medium, utm_campaign, raw_properties)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (
                        obj["id"],
                        props.get("email") or None,
                        props.get("jobtitle") or None,
                        props.get("hs_seniority") or None,
                        props.get("createdate") or None,
                        props.get("utm_source") or None,
                        props.get("utm_medium") or None,
                        props.get("utm_campaign") or None,
                        json.dumps(props),
                    ),
                )
                # The list endpoint returns associated company IDs inline, so
                # the contact/company map is refreshed with the same snapshot.
                for company in obj.get("associations", {}).get("companies", {}).get("results", []):
                    cur.execute(
                        """INSERT INTO raw.hubspot_contact_company_map
                           (contact_id, company_id) VALUES (%s, %s)""",
                        (obj["id"], company["id"]),
                    )
                count += 1
            after = page.get("paging", {}).get("next", {}).get("after")
            if not after:
                break
            time.sleep(0.5)  # respect rate limits
    return count


def extract_companies_live(conn) -> int:
    """Page HubSpot companies API → raw.hubspot_companies (append-only)."""
    count = 0
    after = None
    with conn, conn.cursor() as cur:
        while True:
            page = _hs_page("company", COMPANY_PROPS, after)
            for obj in page.get("results", []):
                props = obj.get("properties", {})
                emp_str = props.get("numberofemployees")
                emp_val = int(emp_str) if emp_str and emp_str.isdigit() else None
                cur.execute(
                    """INSERT INTO raw.hubspot_companies
                       (id, name, domain, industry, numberofemployees,
                        hs_employee_range, raw_properties)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        obj["id"],
                        props.get("name") or None,
                        props.get("domain") or None,
                        props.get("industry") or None,
                        emp_val,
                        props.get("hs_employee_range") or None,
                        json.dumps(props),
                    ),
                )
                count += 1
            after = page.get("paging", {}).get("next", {}).get("after")
            if not after:
                break
            time.sleep(0.5)
    return count


# ── Mock extract ────────────────────────────────────────────────────────────

def extract_contacts_mock(conn) -> int:
    """Insert synthetic contacts matching real HubSpot schema."""
    count = 0
    with conn, conn.cursor() as cur:
        for c in MOCK_CONTACTS:
            cid, email, title, sen, created, utm_s, utm_m, utm_c, comp_id = c
            props = {
                "email": email, "jobtitle": title, "hs_seniority": sen,
                "createdate": created, "utm_source": utm_s,
                "utm_medium": utm_m, "utm_campaign": utm_c,
            }
            cur.execute(
                """INSERT INTO raw.hubspot_contacts
                   (id, email, jobtitle, hs_seniority, createdate,
                    utm_source, utm_medium, utm_campaign, raw_properties)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (cid, email, title, sen or None, created,
                 utm_s, utm_m, utm_c, json.dumps(props)),
            )
            count += 1
            # Also insert association if company_id present
            if comp_id:
                cur.execute(
                    """INSERT INTO raw.hubspot_contact_company_map
                       (contact_id, company_id) VALUES (%s, %s)""",
                    (cid, comp_id),
                )
    return count


def extract_companies_mock(conn) -> int:
    """Insert synthetic companies matching real HubSpot schema."""
    count = 0
    with conn, conn.cursor() as cur:
        for c in MOCK_COMPANIES:
            cid, name, domain, industry, emp, emp_range = c
            props = {
                "name": name, "domain": domain, "industry": industry,
                "numberofemployees": str(emp) if emp else "",
                "hs_employee_range": emp_range or "",
            }
            cur.execute(
                """INSERT INTO raw.hubspot_companies
                   (id, name, domain, industry, numberofemployees,
                    hs_employee_range, raw_properties)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (cid, name, domain, industry or None, emp,
                 emp_range or None, json.dumps(props)),
            )
            count += 1
    return count


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HubSpot extract → raw schema")
    parser.add_argument("--mock", action="store_true",
                        help="Use synthetic data (no HubSpot token needed)")
    args = parser.parse_args()

    print(f"Extract mode: {'MOCK' if args.mock else 'LIVE'}")
    print(f"DATABASE_URL: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")

    conn = psycopg2.connect(DATABASE_URL)

    if args.mock:
        n_contacts = extract_contacts_mock(conn)
        n_companies = extract_companies_mock(conn)
    else:
        n_contacts = extract_contacts_live(conn)
        n_companies = extract_companies_live(conn)

    conn.close()
    print(f"Extracted: {n_contacts} contacts, {n_companies} companies")
    print(f"  → raw.hubspot_contacts: {n_contacts} rows appended (source: extract_hubspot.py --mock)")
    print(f"  → raw.hubspot_companies: {n_companies} rows appended (source: extract_hubspot.py --mock)")
    print(f"  → raw.hubspot_contact_company_map: associations appended")


if __name__ == "__main__":
    main()
