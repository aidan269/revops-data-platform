# Web and marketing attribution readiness

## Monday answer for Viv

Today the warehouse can connect contact-level original UTMs and HubSpot form
submissions to contact-associated, live-only deals and closed-won outcomes. It
cannot reconstruct website click paths, sessions, anonymous visitors, or a
complete form-to-contact conversion rate. It also cannot identify bot or junk
traffic because no deterministic bot signal is present.

Every investor-facing deal and win count comes from
`mart_gtm_lifecycle_live`, which requires a recent deal extraction and excludes
the six-digit development fixture IDs. Form events and contact UTMs are used in
an investor claim only after their contact is associated with one of those live
deals.

## Evidence treatment

- `clean_utm`: a nonblank source that is not the known malformed
  `utm_source='utm_medium:'` pattern.
- `missing_or_inferred_utm`: no reliable original source is available; the
  channel may be an explicit unknown bucket.
- `corrupted_utm`: the deterministic malformed UTM pattern is present.
- `unavailable_no_associated_contact`: no contact link exists for the live deal.
- `predeal_form_evidence`: at least one contact-linked form submission occurred
  at or before deal creation.
- `form_evidence_after_deal_only`: form evidence exists, but cannot explain deal
  creation because it occurred afterward.
- `no_form_evidence`: an associated contact exists, but no form event exists.
- `website_click_evidence`: unavailable. HubSpot `email_click` events are not
  website-click events and are never relabeled.
- `bot_junk_signal_status`: not assessable. Corrupted or missing UTMs are
  tracking-quality issues, not evidence of a bot.

The models report observed linkage and coverage, not causal attribution. Deal
amount is CRM deal value; it is not automatically ARR.

## Known limitations

- No page-view, website-click, session, anonymous visitor, landing-page, or
  referrer event is present.
- Form submissions have contact ID and timestamp, but no modeled page URL,
  form name/version, session ID, submission status, or consent context.
- Original UTMs are contact properties, not immutable event-level parameters.
- Top-of-funnel contact and form populations cannot independently exclude demo
  records; only live-deal-linked reporting is investor-safe.
- Multi-contact deals can have multiple forms. The detail preserves counts and
  uses one row per live deal rather than pretending each form caused the deal.
- No deterministic bot/junk fields exist, so the output does not label any
  record as bot, spam, or junk.

## Outputs

- `fct_web_attribution_readiness_live`: one row per live deal with contact, form,
  UTM, win, and evidence-quality fields.
- `mart_web_attribution_readiness_live`: coverage by UTM and form-evidence
  status.
- `mart_web_funnel_coverage_live`: seven concise evidence checkpoints.
- `mart_web_marketing_evidence_inventory`: available fields, record counts, and
  safe reporting scope.

These tables are read-only and do not modify tracking or operational systems.
