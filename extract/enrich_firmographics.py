#!/usr/bin/env python3
"""
Enrich mock contacts with firmographics for ICP analysis (Task 6).

The Task 4 mock data generated 14,500 contacts but only the original 12 have
company associations. This script:
  1. Creates additional mock companies with realistic firmographics.
  2. Associates contacts to companies.
  3. Updates contact hs_seniority for a subset (to improve coverage from 1.4%).

This is deterministic (seeded) — re-running produces the same data.
Idempotent: skips contacts that already have company associations.

Usage:
  python enrich_firmographics.py --mock
"""

from __future__ import annotations

import argparse
import json
import os
import random

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")

# Industries from gtm_context.md — software, IT, fintech/crypto over-index
INDUSTRIES = [
    "Software", "Information Technology", "Financial Services",
    "Cryptocurrency/Blockchain", "Cybersecurity", "Healthcare",
    "Manufacturing", "Consulting", "Retail/E-commerce", "Media",
]

# Employee ranges (weighted toward mid-market per gtm_context.md)
EMPLOYEE_RANGES = [
    ("1-10", 5, 1, 10),
    ("11-50", 30, 11, 50),
    ("51-200", 120, 51, 200),
    ("201-500", 350, 201, 500),       # sweet spot
    ("501-1000", 750, 501, 1000),
    ("1001-5000", 2500, 1001, 5000),  # sweet spot
    ("5001-10000", 7500, 5001, 10000),
    ("10001+", 15000, 10001, 50000),
]

EMPLOYEE_WEIGHTS = [5, 10, 10, 20, 10, 20, 10, 5]  # mid-market weighted

# Marquee company names for anchoring (per gtm_context.md)
MARQUEE_COMPANIES = [
    ("Anthropic", "Software", "1001-5000"),
    ("NVIDIA", "Information Technology", "10001+"),
    ("Salesforce", "Software", "10001+"),
    ("Apple", "Information Technology", "10001+"),
    ("Coinbase", "Cryptocurrency/Blockchain", "1001-5000"),
    ("GitLab", "Software", "1001-5000"),
    ("Nord Security", "Cybersecurity", "501-1000"),
    ("SAP", "Software", "10001+"),
    ("Spring", "Software", "11-50"),
    ("Morpho", "Cryptocurrency/Blockchain", "11-50"),
    ("Uniswap", "Cryptocurrency/Blockchain", "51-200"),
    ("Lido", "Cryptocurrency/Blockchain", "11-50"),
    ("Ethena", "Cryptocurrency/Blockchain", "11-50"),
]

# Seniority values to assign (improving coverage from 1.4%)
SENIORITIES = ["executive", "vp", "director", "manager", "senior", "entry"]
SENIORITY_WEIGHTS = [15, 20, 25, 20, 15, 5]  # weighted toward decision-makers

# Job titles by seniority for enrichment
TITLES_BY_SENIORITY = {
    "executive": ["CEO", "CTO", "CISO", "CFO", "Founder", "Chief Security Officer"],
    "vp": ["VP of Engineering", "VP of Security", "VP of Product", "VP of Sales"],
    "director": ["Director of Security", "Director of Engineering", "Head of Security", "Head of Data"],
    "manager": ["Security Manager", "Engineering Manager", "Product Manager"],
    "senior": ["Senior Security Engineer", "Senior Software Engineer", "Staff Engineer"],
    "entry": ["Security Analyst", "Junior Engineer", "Analyst"],
}


def main():
    parser = argparse.ArgumentParser(description="Enrich mock firmographics for ICP")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    random.seed(42)
    conn = psycopg2.connect(DATABASE_URL)

    # 1. Check which contacts already have company associations
    with conn.cursor() as cur:
        cur.execute("""
            SELECT contact_id FROM analytics_analytics.dim_contact
            WHERE company_id IS NOT NULL
        """)
        already_associated = {r[0] for r in cur.fetchall()}

        cur.execute("SELECT id FROM raw.hubspot_contacts ORDER BY id")
        all_contact_ids = [r[0] for r in cur.fetchall()]

    to_enrich = [cid for cid in all_contact_ids if cid not in already_associated]
    print(f"Contacts to enrich: {len(to_enrich)} (already associated: {len(already_associated)})")

    # 2. Create marquee + mock companies
    next_company_id = 100000
    companies = []

    # Add marquee companies first
    for name, industry, emp_range in MARQUEE_COMPANIES:
        range_info = next(er for er in EMPLOYEE_RANGES if er[0] == emp_range)
        companies.append({
            "id": str(next_company_id),
            "name": name,
            "domain": name.lower().replace(" ", "") + ".com",
            "industry": industry,
            "numberofemployees": range_info[1],
            "hs_employee_range": emp_range,
        })
        next_company_id += 1

    # Add mock companies (one per ~5 contacts)
    n_mock_companies = len(to_enrich) // 5 + 100
    for i in range(n_mock_companies):
        emp_range_data = random.choices(
            list(zip(EMPLOYEE_RANGES, EMPLOYEE_WEIGHTS)),
            weights=EMPLOYEE_WEIGHTS
        )[0][0]
        emp_range, emp_mid, emp_min, emp_max = emp_range_data
        industry = random.choice(INDUSTRIES)
        companies.append({
            "id": str(next_company_id + i),
            "name": f"Company {next_company_id + i}",
            "domain": f"company{next_company_id + i}.com",
            "industry": industry,
            "numberofemployees": random.randint(emp_min, emp_max),
            "hs_employee_range": emp_range,
        })
    next_company_id += n_mock_companies

    # 3. Insert companies (skip existing)
    companies_inserted = 0
    with conn.cursor() as cur:
        for c in companies:
            cur.execute(
                """INSERT INTO raw.hubspot_companies
                   (id, name, domain, industry, numberofemployees, hs_employee_range, raw_properties)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (c["id"], c["name"], c["domain"], c["industry"],
                 c["numberofemployees"], c["hs_employee_range"],
                 json.dumps(c)),
            )
            companies_inserted += 1

    # 4. Associate contacts to companies
    associations_inserted = 0
    with conn.cursor() as cur:
        for cid in to_enrich:
            # Assign to a company (marquee companies get ~3% of contacts)
            if random.random() < 0.03:
                company = random.choice(companies[:len(MARQUEE_COMPANIES)])
            else:
                company = random.choice(companies[len(MARQUEE_COMPANIES):])
            cur.execute(
                """INSERT INTO raw.hubspot_contact_company_map
                   (contact_id, company_id) VALUES (%s, %s)
                   ON CONFLICT DO NOTHING""",
                (cid, company["id"]),
            )
            associations_inserted += 1

    # 5. Enrich seniority for ~30% of contacts (improving from 1.4%)
    seniority_updated = 0
    with conn.cursor() as cur:
        for cid in to_enrich:
            if random.random() < 0.30:
                sen_idx = random.choices(range(len(SENIORITIES)), weights=SENIORITY_WEIGHTS)[0]
                seniority = SENIORITIES[sen_idx]
                title = random.choice(TITLES_BY_SENIORITY[seniority])
                # Insert a new snapshot row with seniority + jobtitle
                cur.execute(
                    """INSERT INTO raw.hubspot_contacts
                       (id, hs_seniority, jobtitle, raw_properties)
                       VALUES (%s, %s, %s, %s)""",
                    (cid, seniority, title, json.dumps({"hs_seniority": seniority, "jobtitle": title})),
                )
                seniority_updated += 1

    conn.commit()
    conn.close()

    print(f"Companies inserted: {companies_inserted}")
    print(f"Associations inserted: {associations_inserted}")
    print(f"Seniority enriched: {seniority_updated}")

    # Report coverage
    conn2 = psycopg2.connect(DATABASE_URL)
    with conn2.cursor() as cur:
        cur.execute("""SELECT count(*) FROM raw.hubspot_contacts WHERE hs_seniority IS NOT NULL AND hs_seniority != ''""")
        n_sen = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM raw.hubspot_contacts")
        n_total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM raw.hubspot_contact_company_map")
        n_assoc = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM raw.hubspot_companies")
        n_comp = cur.fetchone()[0]
    conn2.close()
    print(f"\nCoverage after enrichment:")
    print(f"  Contacts with seniority: {n_sen}/{n_total} ({n_sen/n_total*100:.1f}%)")
    print(f"  Contact-company associations: {n_assoc}")
    print(f"  Total companies: {n_comp}")


if __name__ == "__main__":
    main()
