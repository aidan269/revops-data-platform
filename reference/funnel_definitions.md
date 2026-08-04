# Funnel Definitions — Channel Taxonomy & Conversion Logic

## Channel taxonomy (first-touch, from original UTM source)

Maps `utm_source` values to high-level channels for funnel analysis. This is the
**first-touch** model: the channel is assigned from the contact's original UTM
`utm_source` at form submission. Last-touch and multi-touch come in Task 5.

| Channel | utm_source values |
|---------|-------------------|
| Google Ads | `google`, `googleads.g.doubleclick.net` |
| LinkedIn | `linkedin` |
| X / Twitter | `twitter`, `twitter.com`, `t.co`, `x` |
| Organic Search | `bing`, `duckduckgo`, `ecosia` |
| Community / Social | `reddit`, `chatgpt.com`, `superteam.fun`, `bnbchain.org` |
| Email / In-app | `mail`, `hs_email`, `in-app` |
| Webflow / Cantina | `cantina-staging.webflow.io`, `cantina.website`, `webflow.com`, `cantina-prod.us.auth0.com`, `46025408.hs-sites.com` |
| Referral / Partner | `spearbit.com`, `theblock.co`, `morpho.org`, `github.com`, `medium.com`, `ethereum.org`, `lu.ma`, `luma.com`, `blog.lido.fi`, `docs.ethena.fi`, `docs.megapot.io`, `docs.size.credit`, `eggs-finance.gitbook.io`, `hub.forum.berachain.com`, `uniswapfoundation.org`, `solaxy.io` |
| Press / Media | `cloudseclist`, `companionlink.com`, `techbullion.com`, `onlinethreatalerts.com`, `eqchi.r.ag.d.sendibm3.com` |
| Direct | `direct` |
| Organic (unspecified) | `organic` |
| Referral (generic) | `referral` |
| **Unknown (corrupted UTM)** | `utm_medium:` and any value not in the accepted set |

## Malformed UTMs

The corrupted UTM pattern is `utm_source = "utm_medium:"` — a mapping bug that
shifted every field one position over. These 138 records are carried as their
own **"Unknown (corrupted UTM)"** channel bucket so they never silently
disappear into another channel. This is the regression guard: the mart must
always show exactly 138 contacts in this bucket.

## Win attribution

- `hs_is_closed_won` is carried through from HubSpot as-is — never re-derived
  from `dealstage` labels. Stage names change; the boolean is the source of truth.
- A contact's channel is assigned from their first-touch UTM. Deals inherit
  the channel from the associated contact via `bridge_deal_contact`.
- Win rate = `won / contacts` (primary) and `won / deals` (secondary).
- Pipeline $ = sum of `amount` for all deals.
- Won $ = sum of `amount` for deals where `hs_is_closed_won = true`.

## Regression guards

- Total `hs_is_closed_won = true` across the mart ≈ **1,885** (known HubSpot count).
- Unknown (corrupted UTM) bucket = **138** contacts (the historical corruption).
- If either drifts, the dbt test fails loudly — the mapping or extract changed.
