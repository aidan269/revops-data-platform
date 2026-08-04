# Job: Attribution debugging

**Goal:** find and explain attribution anomalies (bad UTMs, source spikes, missing
campaign links) from curated data. Surface fixes; never edit raw.

**Steps**

1. Query `analytics.fct_touchpoint` / `analytics.mart_attribution`.
2. Run the checks: `utm_source` not in the accepted set, null-source spikes, sudden channel
   shifts, deals with no campaign source, same-day/0-day "deals" polluting win-rate.
3. Produce a short written finding: exact counts, date range, and the table/column behind
   each number. Recommend the dbt/source fix — do not patch raw.

**Reference case (the alarm that should never miss again)**

The 138 corrupted records were `utm_source = "utm_medium:"` — a mapping bug shifting every
value one field over, spanning **Nov 2024 – May 2025**, then zero once Make replaced the old
Zapier feed. The `accepted_values` test on `utm_source` catches that whole class on day one
instead of 15 months later.
