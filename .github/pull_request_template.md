<!--
Reviewer block. Gerald fills this in on every PR. The reviewer approves OUTCOMES and
GUARDRAILS, not raw SQL — the dbt tests cover correctness. Keep it readable by a non-developer.
-->

**Notion task:** <!-- paste the Notion task page URL -->

## What changed (plain English)
<!-- 2–4 sentences: what this task built and why it matters. No jargon. -->

## Verification evidence
<!-- The proof it works. e.g. "26/26 checks passed. dbt build: 26 pass / 0 error.
     Reconciliations: closed-won = 1,885 ✓, corrupted-UTM bucket = 138 ✓." -->

## Guardrail status
- [ ] Read-only (no HubSpot writes) — OR — live write ran through `writeback/hubspot_writer.py`
- [ ] If a write ran: whitelist enforced, dry-run reviewed first, every change logged to `analytics.hubspot_writeback_log`, human approval recorded
- [ ] No non-whitelisted field touched; no non-empty field overwritten

## 👉 What to eyeball
<!-- The 1–3 specific things you want the human to sanity-check before approving.
     e.g. "Do the top-3 channels by win rate look right?" Point at the readout CSV. -->

---
**How to approve:** review the above, then set this task's **Status → Signed Off** in the
🏊 Tasks board. Do **not** click Merge here — the merge happens automatically from that sign-off.
