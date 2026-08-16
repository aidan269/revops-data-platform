# Investor customer-motion methodology

## What the reporting can claim

Investor-facing customer-motion reporting uses only closed-won deals in
`mart_gtm_lifecycle_live`. That model requires a recent raw HubSpot extraction
and live-format deal IDs, excluding the repository's six-digit demo fixtures.

A deal is reported as brand-new client ARR (`net_new_arr`), audit-to-ARR
conversion, or expansion only when `gtm_deal_motion_overrides.csv` contains a
reviewed classification with an evidence note, reviewer, and review date.
Company history is never sufficient classification evidence. A first known win
may still be audit-only or non-recurring work; a repeat win may be a renewal,
audit conversion, expansion, or unrelated non-ARR work.

`amount` is a CRM deal amount. It is exposed as `classified_arr_amount` only for
the three ARR motions after review. Until Finance confirms that deal amount is
the correct ARR basis, the reporting must not describe unclassified deal amount
as ARR.

## Outputs

- `fct_customer_motion_live`: one row per live closed-won deal and the audit
  spine for all reporting.
- `mart_customer_motion_reporting_live`: counts, deal amounts, classified ARR
  amounts, measurement status, and reviewed-evidence coverage.
- `mart_new_client_source_live`: first-touch source for reviewed brand-new ARR
  only. An empty table means new-client source is not yet measurable.
- `mart_customer_motion_review_queue_live`: every unresolved deal, available
  evidence, and the next reviewer action. It does not write to any operational
  system.

## Evidence required from Sales, CS, and Finance

For each queued deal, Viv needs:

1. Sales/CS: the direct company association and whether the customer was new at
   close.
2. Sales/CS: current and prior product/service or statement-of-work lineage,
   including whether an audit preceded the ARR contract.
3. Finance: signed-contract support, recurring versus non-recurring status, the
   ARR amount and effective period, and whether a repeat deal is expansion or
   renewal.
4. A named reviewer, review date, and concise evidence note entered in
   `seeds/gtm_deal_motion_overrides.csv` using one of:
   `net_new_arr`, `audit_to_arr_conversion`, `expansion`, `renewal`, or
   `other_non_arr`.

After review, run `dbt seed --profiles-dir .` followed by `dbt build
--profiles-dir .`. Do not add an override when evidence is ambiguous; leave the
deal unclassified.

## Known limitations

- The current warehouse lacks authoritative product/service lineage and a
  Finance-grade ARR schedule.
- First-touch attribution is contact-based and may be missing or corrupted.
- Company history is calculated only across live deal records in the reporting
  fact, preventing demo fixtures from influencing investor evidence.
- Closed-won deal amount is not assumed to equal ARR until the reviewed motion
  and Finance evidence support that treatment.
