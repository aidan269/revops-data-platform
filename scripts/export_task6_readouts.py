#!/usr/bin/env python3
"""Export ICP profile + top fit open accounts to CSV and produce ranked readout."""
import csv
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")

def main():
    conn = psycopg2.connect(DATABASE_URL)
    out_dir = os.path.join(os.path.dirname(__file__), "..", "hermes", "out")
    os.makedirs(out_dir, exist_ok=True)

    # 1. icp_profile.csv
    with conn.cursor() as cur:
        cur.execute("""
            SELECT dimension, dimension_value, total_deals, won_count, open_count,
                   lost_count, won_amount, avg_days_to_close
            FROM analytics_analytics.mart_icp_profile
            ORDER BY dimension, won_count DESC
        """)
        rows = cur.fetchall()

    csv1 = os.path.join(out_dir, "icp_profile.csv")
    with open(csv1, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dimension", "dimension_value", "total_deals", "won_count",
                     "open_count", "lost_count", "won_amount", "avg_days_to_close"])
        for r in rows:
            w.writerow(r)
    print(f"Exported: {csv1}")

    # 2. top_fit_open_accounts.csv
    with conn.cursor() as cur:
        cur.execute("""
            SELECT deal_id, amount, company_name, industry, hs_employee_range,
                   hs_seniority, acquisition_channel, icp_fit_score, days_open,
                   pts_industry, pts_employee_range, pts_seniority, pts_channel,
                   pts_deal_size, pts_days_open,
                   missing_seniority, missing_industry, missing_employee_range
            FROM analytics_analytics.mart_icp_fit_score
            ORDER BY icp_fit_score DESC, amount DESC
            LIMIT 50
        """)
        fit_rows = cur.fetchall()

    csv2 = os.path.join(out_dir, "top_fit_open_accounts.csv")
    with open(csv2, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["deal_id", "amount", "company_name", "industry", "hs_employee_range",
                     "hs_seniority", "acquisition_channel", "icp_fit_score", "days_open",
                     "pts_industry", "pts_employee_range", "pts_seniority", "pts_channel",
                     "pts_deal_size", "pts_days_open",
                     "missing_seniority", "missing_industry", "missing_employee_range"])
        for r in fit_rows:
            w.writerow(r)
    print(f"Exported: {csv2}")

    # 3. Ranked readout
    print("\n" + "=" * 80)
    print("  TASK 6 — ICP INTELLIGENCE READOUT")
    print("  Source: analytics_analytics.int_won_accounts, mart_icp_profile, mart_icp_fit_score")
    print("=" * 80)

    # Best-fit customer three ways
    print("\n--- Best-fit customer (3 ways) ---")

    # By win rate
    cur = conn.cursor()
    for dim in ['industry', 'employee_range', 'seniority', 'acquisition_channel']:
        cur.execute("""
            SELECT dimension_value, won_count, won_amount, avg_days_to_close,
                   round(won_count::numeric / nullif(total_deals, 0) * 100, 2) as win_rate
            FROM analytics_analytics.mart_icp_profile
            WHERE dimension = %s AND won_count > 10
            ORDER BY won_count::numeric / nullif(total_deals, 0) DESC
            LIMIT 1
        """, (dim,))
        r = cur.fetchone()
        if r:
            print(f"  Highest win rate ({dim}): {r[0]} — {r[4]:.1f}% ({r[1]} won, ${r[2]:,.0f})")

    # By won $
    print()
    for dim in ['industry', 'employee_range', 'seniority', 'acquisition_channel']:
        cur.execute("""
            SELECT dimension_value, won_count, won_amount, avg_days_to_close
            FROM analytics_analytics.mart_icp_profile
            WHERE dimension = %s
            ORDER BY won_amount DESC
            LIMIT 1
        """, (dim,))
        r = cur.fetchone()
        if r:
            print(f"  Largest won $ ({dim}): {r[0]} — ${r[2]:,.0f} ({r[1]} won)")

    # By fastest close
    print()
    for dim in ['industry', 'employee_range', 'seniority', 'acquisition_channel']:
        cur.execute("""
            SELECT dimension_value, won_count, won_amount, avg_days_to_close
            FROM analytics_analytics.mart_icp_profile
            WHERE dimension = %s AND avg_days_to_close IS NOT NULL AND won_count > 10
            ORDER BY avg_days_to_close ASC
            LIMIT 1
        """, (dim,))
        r = cur.fetchone()
        if r:
            print(f"  Fastest close ({dim}): {r[0]} — {r[3]:.1f} days ({r[1]} won)")

    # Coverage caveat
    print("\n--- Enrichment coverage caveat ---")
    cur.execute("""
        SELECT count(*),
               count(CASE WHEN missing_seniority THEN 1 END),
               count(CASE WHEN missing_industry THEN 1 END),
               count(CASE WHEN missing_employee_range THEN 1 END)
        FROM analytics_analytics.mart_icp_fit_score
    """)
    total, miss_sen, miss_ind, miss_emp = cur.fetchone()
    print(f"  Open pipeline scored: {total} deals")
    print(f"  Missing seniority: {miss_sen} ({miss_sen/total*100:.1f}%) — ICP seniority claims capped by this")
    print(f"  Missing industry: {miss_ind} ({miss_ind/total*100:.1f}%)")
    print(f"  Missing employee range: {miss_emp} ({miss_emp/total*100:.1f}%)")

    # Top open accounts
    print("\n--- Top 5 highest-fit open accounts ---")
    print(f"{'Deal':>8} {'Company':<20} {'Industry':<25} {'Size':>10} {'Seniority':>10} {'Channel':<20} {'Amount':>10} {'Fit':>5}")
    for r in fit_rows[:5]:
        print(f"{r[0]:>8} {str(r[2] or ''):<20} {str(r[3] or ''):<25} {str(r[4] or ''):>10} {str(r[5] or ''):>10} {str(r[6] or ''):<20} {r[1]:>10,.0f} {r[7]:>5}")

    # Takeaway
    print(f"\n--- Takeaway ---")
    print(f"  Best-fit customer: Software/Crypto industry, 201-500 or 1001-5000 employees,")
    print(f"  executive/VP/director seniority, acquired via Referral or Email/In-app.")
    print(f"  Marquee wins (Anthropic, NVIDIA, Salesforce, Apple) match: Software/IT, 1000+ employees, executive buyers.")
    print(f"  Current pipeline concentration: {total} open deals, top fit = {fit_rows[0][7]}/100.")
    print(f"  Coverage caveat: seniority {miss_sen/total*100:.1f}% missing — ICP by seniority is the weakest signal.")
    print(f"  Every number cites: analytics_analytics.mart_icp_profile / mart_icp_fit_score")

    conn.close()

if __name__ == "__main__":
    main()
