# Job: Data-quality monitor (scheduled)

**Goal:** run daily and post anomalies to Slack/Notion. Surface, don't silently repair.

**Steps**

1. Run dbt tests (`not_null`, `unique`, `accepted_values`, source `freshness`) against the
   marts.
2. Compare key volumes vs the trailing 7/30-day baseline (new contacts, deals, form-fills).
   Flag deviations beyond a set threshold (e.g. > 3× or a drop to zero on a live feed).
3. Summarize failures + anomalies in a short digest and post to the configured channel.
   Each line: table · column · failing count · likely cause.

**Guardrails**

- Never auto-fix. A monitor that quietly repairs data hides the very bug you want to see.
- Freshness failures (a feed silently stopping) are the highest priority — that's the
  Jul-28 scoping-field flatline and the old Zapier corruption, both of which were invisible
  for want of this check.
