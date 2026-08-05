# Funnel & attribution definitions (canonical)

Every funnel/attribution mart reads these definitions. They are version-controlled here so a
number never depends on how someone happened to name a stage. Cite the table/column behind
each figure (see system.md).

## Win / conversion
- Closed-won = `hs_is_closed_won = true`. This is authoritative (~1,885 deals). NEVER count
  wins by the dealstage label "Closed Won" — that label gives ~197 and is wrong.
- Pipeline created = a deal exists (any open or closed stage) associated to the contact.
- Days-to-close = closedate - createdate on won deals (baseline ~13 days; sanity check only).

## Funnel stages (lifecycle)
Lead created -> MQL -> SQL/Opportunity (deal created) -> Closed-won. Derive stage from HubSpot
lifecyclestage + deal existence. Report counts and stage-to-stage conversion rates.

## Channel taxonomy (deterministic UTM -> channel), first match wins
- utm_medium in (cpc, ppc, paid, paidsearch) -> Paid Search
- utm_medium in (paid-social, paidsocial, social-paid) -> Paid Social
- utm_medium in (social, organic-social) -> Organic Social
- utm_medium = email -> Email
- utm_medium in (organic, seo) -> Organic Search
- utm_medium = referral -> Referral
- utm_medium in (event, field) OR utm_campaign matches a known event (e.g. blackhat) -> Event
- utm_source = apollo -> Outbound
- null / (direct) / (none) -> Direct
- anything else, or malformed -> Unknown

## Corrupted-UTM handling (hard rule)
The 138 malformed-UTM records (old Zapier feed) are unrecoverable. Bucket them as
"Unknown (corrupted UTM)", report as their own line, never attribute to a real channel.
A regression test asserts this bucket = 138.

## Attribution models (build all three; pick at query time)
- First-touch — 100% credit to acquisition touch (contact original UTM).
- Last-touch — 100% credit to the touch before the deal was created.
- Linear multi-touch — credit split evenly across all touches; fairest default for readouts.

## Messaging theme
Campaign name / email subject classified into a small controlled vocabulary (product-launch,
event-invite, webinar, case-study, security-research, pricing, nurture). Advisory and
model-assisted (Ollama); the raw campaign/subject is always preserved. Never let a theme
label stand in for the source text.
