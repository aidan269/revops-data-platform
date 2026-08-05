#!/usr/bin/env python3
"""Export campaign type + messaging readouts to CSV."""
import csv
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")

def main():
    conn = psycopg2.connect(DATABASE_URL)
    out_dir = os.path.join(os.path.dirname(__file__), "..", "hermes", "out")
    os.makedirs(out_dir, exist_ok=True)

    # 1. campaign_type_performance.csv
    with conn.cursor() as cur:
        cur.execute("""
            SELECT campaign_type,
                   count(*) as campaigns,
                   sum(touchpoints) as touchpoints,
                   sum(contacts_influenced) as contacts,
                   sum(pipeline_influenced) as pipeline_dollars,
                   sum(won_amount) as won_dollars,
                   sum(closed_won_influenced) as closed_won,
                   round(avg(win_rate) * 100, 2) as avg_win_rate_pct
            FROM analytics_analytics.mart_campaign_performance
            GROUP BY campaign_type
            ORDER BY won_dollars DESC
        """)
        rows = cur.fetchall()

    csv1 = os.path.join(out_dir, "campaign_type_performance.csv")
    with open(csv1, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["campaign_type", "campaigns", "touchpoints", "contacts",
                     "pipeline_dollars", "won_dollars", "closed_won", "avg_win_rate_pct"])
        for r in rows:
            w.writerow(r)
    print(f"Exported: {csv1}")

    # 2. messaging_resonance.csv
    with conn.cursor() as cur:
        cur.execute("""
            SELECT messaging_theme, total_touchpoints, email_opens, email_clicks,
                   round(click_to_open_rate, 2) as ctr_pct,
                   contacts_engaged, contacts_influenced,
                   pipeline_influenced, won_amount,
                   round(conversion_rate * 100, 2) as conv_rate_pct
            FROM analytics_analytics.mart_messaging
            ORDER BY won_amount DESC
        """)
        rows2 = cur.fetchall()

    csv2 = os.path.join(out_dir, "messaging_resonance.csv")
    with open(csv2, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["messaging_theme", "total_touchpoints", "email_opens", "email_clicks",
                     "ctr_pct", "contacts_engaged", "contacts_influenced",
                     "pipeline_influenced", "won_amount", "conv_rate_pct"])
        for r in rows2:
            w.writerow(r)
    print(f"Exported: {csv2}")

    # 3. Ranked readout
    print("\n" + "=" * 80)
    print("  TASK 5 RANKED READOUT")
    print("  Source: analytics_analytics.mart_campaign_performance, analytics_analytics.mart_messaging")
    print("=" * 80)

    print("\n--- Campaign Type by Won $ ---")
    print(f"{'Type':<20} {'Won $':>16} {'Win Rate':>10} {'Campaigns':>10}")
    for r in rows:
        print(f"{r[0]:<20} {r[5]:>16,.0f} {r[7]:>9.2f}% {r[1]:>10}")

    print("\n--- Messaging Themes by Engagement (touchpoints) ---")
    print(f"{'Theme':<20} {'Touchpoints':>12} {'Engaged':>10} {'CTR%':>8}")
    for r in rows2:
        print(f"{r[0]:<20} {r[1]:>12} {r[5]:>10} {r[4]:>7.1f}%")

    print("\n--- Messaging Themes by Conversion (won $) ---")
    print(f"{'Theme':<20} {'Won $':>14} {'Conv Rate':>10}")
    for r in rows2:
        print(f"{r[0]:<20} {r[8]:>14,.0f} {r[9]:>9.2f}%")

    # Flag: engages but doesn't convert
    print("\n--- Flag: Engages but doesn't convert ---")
    for r in rows2:
        theme, touches, opens, clicks, ctr, engaged, influenced, pipe, won, conv = r
        if engaged > 0 and (influenced or 0) == 0:
            print(f"  ⚠️  {theme}: {engaged} engaged but 0 influenced — high engagement, no conversion")
    # Check for low conversion despite high engagement
    for r in rows2:
        theme, touches, opens, clicks, ctr, engaged, influenced, pipe, won, conv = r
        if (engaged or 0) > 3000 and (conv or 0) < 22.0:
            print(f"  ⚠️  {theme}: {engaged} engaged, only {conv:.1f}% conversion — engages but converts poorly")

    print(f"\n--- Takeaway ---")
    top_type = rows[0]
    print(f"  Best campaign type by won $: {top_type[0]} (${top_type[5]:,.0f}, {top_type[7]:.1f}% win rate)")
    top_theme_won = rows2[0]
    print(f"  Top messaging theme by won $: {top_theme_won[0]} (${top_theme_won[8]:,.0f})")
    print(f"  Every number cites: analytics_analytics.mart_campaign_performance / mart_messaging")

    conn.close()

if __name__ == "__main__":
    main()
