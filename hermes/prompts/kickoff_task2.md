# Kickoff — Task 2: HubSpot extract, first marts, guarded writeback (dry-run)

Follow system.md. Deterministic. **Writeback runs DRY-RUN ONLY in this task — no live
HubSpot writes.** Report row counts + a sample of logged dry-run diffs at the end.

## A. Extract HubSpot into raw
1. Set `HUBSPOT_PRIVATE_APP_TOKEN` (read scope for this part).
2. Write a Python extract that pages the HubSpot API and lands:
   - `raw.hubspot_contacts`: id, email, jobtitle, hs_seniority, createdate, utm_source,
     utm_medium, utm_campaign.
   - `raw.hubspot_companies`: id, name, domain, industry, numberofemployees, hs_employee_range.
   Append-only with an `extracted_at` timestamp (snapshot pattern).

## B. First marts (dbt)
3. Model `dim_contact` / `dim_company` from the latest snapshot per id.
4. Build `mart_enrichment_gaps`: one row per contact/company with a boolean gap flag per
   target field (hs_seniority, industry, hs_employee_range). This is what the CRM-enrichment
   job reads. (Baseline to beat: seniority 1.4%, industry 68%, employee_range 21%.)
5. Add tests (not_null on ids; accepted_values where sensible). `dbt build`.

## C. Guarded writeback (dry-run only)
6. Use `writeback/hubspot_writer.py`. Confirm the WHITELIST (hs_seniority, icp_fit,
   black_hat_lead_grade) and that a non-whitelisted field is **refused** (test it).
7. For 3 sample contacts from `mart_enrichment_gaps`, derive `hs_seniority` from `jobtitle`
   deterministically (simple mapping first; use the local/hosted model only for ambiguous
   titles). Call `write_fields("contact", id, {"hs_seniority": ...}, dry_run=True)`.
8. Confirm the diffs are written to `analytics.hubspot_writeback_log` and **nothing** was
   sent to HubSpot.

Success = HubSpot data in the warehouse, `dim_*` + `mart_enrichment_gaps` built, and the
writeback proven safe in dry-run (whitelist enforced, diffs logged, zero live writes).

Task 3 will flip a small, human-approved batch to a live write and then wire the scheduled
data-quality monitor.
