<!--
Reviewer block. Gerald fills this in on every PR. The reviewer approves OUTCOMES and
GUARDRAILS, not raw SQL — the dbt tests cover correctness. Keep it readable by a non-developer.
-->

## What changed (plain English)
<!-- 2–4 sentences: what this task built and why it matters. No jargon. -->

## Verification evidence
<!-- The proof it works. e.g. "26/26 checks passed. dbt build: 26 pass / 0 error.
     Reconciliations: closed-won = 1,885 ✓, corrupted-UTM bucket = 138 ✓." -->

**Evidence-dependent suites run locally?** <!-- Required. CI runs only the portable subset:
     the suites that read hermes_shared/artifacts, ledger and execution_packages skip there,
     so ~85 tests are invisible to CI. Run `pytest tests/ -q` on a checkout WITH operational
     evidence present and paste the counts (passed / failed / skipped), or state why not. -->

## Guardrail status
- [ ] Read-only (no HubSpot writes) — OR — live write ran through `writeback/hubspot_writer.py`
- [ ] If a write ran: whitelist enforced, dry-run reviewed first, every change logged to `analytics.hubspot_writeback_log`, human approval recorded
- [ ] No non-whitelisted field touched; no non-empty field overwritten

## 👉 What to eyeball
<!-- The 1–3 specific things you want the human to sanity-check before approving.
     e.g. "Do the top-3 channels by win rate look right?" Point at the readout CSV. -->

---
**Approval:** approval is a **GitHub PR review on this pull request**. The author never
approves and never merges their own PR — merge only after another reviewer has left an
approving review.

**What approval covers:** approving this PR approves **code only**. It does **not** authorize
any CRM mutation. Executing a change against live CRM records requires a separate, explicit
approval that names the exact proposal and target population — see step 3 of
`hermes_shared/HANDOFF_PROTOCOL.md`.
