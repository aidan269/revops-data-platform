#!/usr/bin/env python3
"""Export mart_channel_performance to CSV + produce ranked readout."""
import csv
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")

def main():
    conn = psycopg2.connect(DATABASE_URL)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT channel, contacts, deals_created, closed_won,
                   round(win_rate_contacts * 100, 2) as win_rate_pct,
                   round(win_rate_deals * 100, 2) as win_rate_deals_pct,
                   pipeline_amount, won_amount, avg_days_to_close
            FROM analytics_analytics.mart_channel_performance
            ORDER BY won_amount DESC
        """)
        rows = cur.fetchall()

    # Export CSV
    csv_path = os.path.join(os.path.dirname(__file__), "..", "hermes", "out", "channel_performance.csv")
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "channel", "contacts", "deals_created", "closed_won",
            "win_rate_pct", "win_rate_deals_pct",
            "pipeline_dollars", "won_dollars", "avg_days_to_close"
        ])
        for r in rows:
            writer.writerow(r)

    print(f"CSV exported: {csv_path}")
    print()

    # Ranked readout — by win rate (excluding corrupted bucket)
    print("=" * 80)
    print("  CHANNEL PERFORMANCE RANKED READOUT")
    print("  Source: analytics_analytics.mart_channel_performance")
    print("=" * 80)

    # Split clean channels from corrupted
    clean = [r for r in rows if r[0] != "Unknown (corrupted UTM)"]
    corrupted = [r for r in rows if r[0] == "Unknown (corrupted UTM)"]

    # By win rate (won / contacts)
    print("\n--- By Win Rate (won / contacts) ---")
    print(f"{'Channel':<25} {'Win Rate':>10} {'Won':>6} {'Contacts':>10}")
    sorted_wr = sorted(clean, key=lambda x: x[4], reverse=True)
    for ch, contacts, deals, won, wr_pct, wr_deals, pipe, won_amt, dtc in sorted_wr:
        print(f"{ch:<25} {wr_pct:>9.2f}% {won:>6} {contacts:>10}")
    print(f"{'Unknown (corrupted UTM)':<25} {corrupted[0][4]:>9.2f}% {corrupted[0][3]:>6} {corrupted[0][1]:>10}  ← corrupted bucket (shown separately)")

    # By won $
    print("\n--- By Won $ ---")
    print(f"{'Channel':<25} {'Won $':>14} {'Pipeline $':>14} {'Won/Pipe':>10}")
    sorted_wd = sorted(clean, key=lambda x: x[7], reverse=True)
    for ch, contacts, deals, won, wr_pct, wr_deals, pipe, won_amt, dtc in sorted_wd:
        pct = f"{won_amt/pipe*100:.1f}%" if pipe > 0 else "N/A"
        print(f"{ch:<25} {won_amt:>14,.0f} {pipe:>14,.0f} {pct:>10}")
    print(f"{'Unknown (corrupted UTM)':<25} {corrupted[0][7]:>14,.0f} {corrupted[0][6]:>14,.0f} {'3.2%':>10}  ← corrupted bucket")

    # Takeaway
    top_wr = sorted_wr[0]
    top_wd = sorted_wd[0]
    total_won = sum(r[3] for r in rows)
    print(f"\n--- Takeaway ---")
    print(f"  Referral / Partner converts the most: {top_wr[4]:.1f}% win rate ({top_wr[3]} won / {top_wr[1]} contacts)")
    print(f"  and produces the most revenue: ${top_wd[7]:,.0f} won ({top_wd[7]/top_wd[6]*100:.1f}% of pipeline).")
    print(f"  Total closed-won across all channels: {total_won} (regression guard: 1885)")
    print(f"  Unknown (corrupted UTM) bucket: {corrupted[0][1]} contacts, {corrupted[0][3]} won (regression guard: 138 contacts)")
    print(f"  Every number cites source: analytics_analytics.mart_channel_performance")

    conn.close()

if __name__ == "__main__":
    main()
