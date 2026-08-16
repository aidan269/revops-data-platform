# Minimum tracking-gap specification

This is a specification only. It does not implement website, CRM, Zapier, or
analytics changes.

## Required events

1. `page_view`
2. `website_click`
3. `form_view`
4. `form_submit_attempt`
5. `form_submit_success`
6. `contact_created_or_matched`

Each event needs an immutable `event_id`, UTC `event_timestamp`, `event_name`,
`anonymous_id`, and `session_id`. Once known, include `contact_id`; never use
email as the event key. Preserve the ID bridge from anonymous visitor and
session to contact rather than overwriting history.

## Required page, click, and form properties

- `page_url`, `page_path`, `page_title`, `referrer_url`
- `link_url`, `link_text`, `link_id` for clicks
- `form_id`, `form_name`, `form_version`, `form_page_url`
- `submission_id`, `submission_status`, `validation_error_code`
- `consent_status` and `consent_timestamp`

## Required campaign parameters

Capture event-level and first-touch values for:

- `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`
- `gclid`, `gbraid`, `wbraid`, `msclkid`, `fbclid`, `li_fat_id`
- normalized `channel` plus a versioned `channel_mapping_version`

Store raw values alongside normalized values. Never parse one UTM field into
another, and never replace a captured first touch with a later touch.

## Deterministic bot/junk evidence

Store the evidence, not a guessed label:

- consented/approved IP-derived bot classification or edge-provider bot score
- parsed `user_agent` classification
- CAPTCHA provider, result, and score
- honeypot triggered boolean
- form submission rate-limit result
- email validation result and reason
- internal QA/test marker
- downstream spam disposition, reason, reviewer, and timestamp

Derive `bot_junk_status` only from documented rules over these fields, retaining
the triggering rule and source value. Missing UTMs, high activity, free email
domains, or unusual conversion rates alone are not bot evidence.

## Required CRM/warehouse joins

- Durable `contact_id` on successful form/contact match
- Complete deal-contact association history with effective timestamps
- Deal creation, stage-change, and closed-won events
- Campaign/ad identifiers at event grain
- Source extraction timestamp and tracking schema version

The shortest trustworthy path is: implement immutable event/session IDs and the
anonymous-to-contact bridge; capture successful form submissions with full
event-level UTMs; then add deterministic bot evidence and stage-change history.
