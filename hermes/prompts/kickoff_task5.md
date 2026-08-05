# Kickoff — Task 5: touchpoints, messaging & campaign-type performance + multi-touch attribution

Follow system.md and ../reference/funnel_definitions.md. Deterministic; the model is used ONLY
for advisory messaging-theme classification, never to invent facts. Read-only — no HubSpot
writes. Report table names + row counts at each step.

Answers: which messaging resonates and which campaign type works best — and unlocks last-touch
+ linear multi-touch attribution.

## A. Extend the extract (read scope)
1. Land, append-only with extracted_at:
   - raw.hubspot_campaigns: id, name, type.
   - raw.hubspot_campaign_members: campaign_id, contact_id.
   - raw.hubspot_engagements: contact_id, type (email_open, email_click, form_submission,
     meeting), timestamp, asset/campaign ref where available.
   If the campaigns endpoint is not reachable on the token, STOP and report — do not fabricate.

## B. Marts (dbt)
2. fct_touchpoint: one row per contact-touchpoint — timestamp, channel, campaign_id, asset,
   engagement_type. The spine for attribution.
3. dim_campaign: id/name + type (deterministic from HubSpot) + messaging_theme (advisory,
   model-assisted; raw name always preserved).
4. mart_attribution: per touchpoint, credit under first-touch, last-touch, and linear
   multi-touch; roll up to channel / campaign / campaign-type. First-touch MUST reconcile to
   mart_channel_performance (regression guard).
5. mart_campaign_performance: per campaign and per campaign type — touchpoints, contacts
   influenced, pipeline influenced, closed-won influenced, win rate, won $ (per-$ if spend exists).
6. mart_messaging: per messaging_theme — two lenses: (a) engagement rate (open/click/reply) and
   (b) downstream conversion (influenced pipeline & closed-won). Report both.
7. Tests: not_null on ids; first-touch reconciles to mart_channel_performance; every touch maps
   to a known channel or the Unknown bucket.

## C. Readouts
8. Emit hermes/out/campaign_type_performance.csv, hermes/out/messaging_resonance.csv, and a short
   readout: best campaign type by won $ and win rate; top messaging themes by engagement AND by
   conversion (flag any theme that engages but doesn't convert). Every number names its table/column.

## Success
fct_touchpoint + dim_campaign built, mart_attribution (3 models) reconciling to task4,
campaign-type and messaging readouts produced. No writes.
