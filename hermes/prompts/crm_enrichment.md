# Job: CRM enrichment

**Goal:** fill missing firmographic/seniority fields on curated contacts/companies, then
stage a controlled write-back.

**Steps**

1. Read `analytics.dim_contact` / `analytics.dim_company` for records with the target field
   empty (e.g. `hs_seniority`, `industry`, `hs_employee_range`).
2. Enrich **deterministically** where possible: existing `jobtitle` → seniority mapping,
   `numberofemployees` → employee-range band. Use the local LLM only for fuzzy
   classification (title → seniority), never to invent facts.
3. Write results to `analytics.stg_enrichment` with a **source stamp per field** (so tier
   attribution is knowable — the thing the current Breeze/Apollo setup can't tell you).
4. Stage the write-back: emit the whitelist fields to `writeback/` in **dry-run**. Show the
   diff (record, field, old → new, source). Wait for approval before the live push.

**Guardrails**

- Never overwrite a non-empty field (fill-empty-only).
- Skip personal/free email domains.
- Respect the consent/GDPR gate before any person-level write.
- Baseline first: today's coverage is jobtitle 92%, hs_seniority 1.4%, industry 68%,
  numberofemployees 67%, hs_employee_range 21%. Seniority is the biggest gap — start there.
