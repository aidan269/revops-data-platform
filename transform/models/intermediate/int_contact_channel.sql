-- int_contact_channel — one row per contact with its first-touch channel.
-- Maps utm_source to high-level channel per reference/funnel_definitions.md.
-- Malformed UTMs (utm_source='utm_medium:') → 'Unknown (corrupted UTM)'.
-- Source: analytics_analytics.stg_hubspot_contacts

with contacts as (
    select * from {{ ref('stg_hubspot_contacts') }}
)

select
    contact_id,
    email,
    utm_source,
    case
        -- Corrupted UTM (the 138-row bug pattern)
        when utm_source = 'utm_medium:' then 'Unknown (corrupted UTM)'
        when utm_source is null or utm_source = '' then 'Unknown (no UTM)'
        -- Google Ads
        when lower(utm_source) in ('google', 'googleads.g.doubleclick.net') then 'Google Ads'
        -- LinkedIn
        when lower(utm_source) = 'linkedin' then 'LinkedIn'
        -- X / Twitter
        when lower(utm_source) in ('twitter', 'twitter.com', 't.co', 'x') then 'X / Twitter'
        -- Organic Search
        when lower(utm_source) in ('bing', 'duckduckgo', 'ecosia') then 'Organic Search'
        -- Community / Social
        when lower(utm_source) in ('reddit', 'chatgpt.com', 'superteam.fun', 'bnbchain.org') then 'Community / Social'
        -- Email / In-app
        when lower(utm_source) in ('mail', 'hs_email', 'in-app') then 'Email / In-app'
        -- Webflow / Cantina
        when lower(utm_source) in (
            'cantina-staging.webflow.io', 'cantina.website', 'webflow.com',
            'cantina-prod.us.auth0.com', '46025408.hs-sites.com'
        ) then 'Webflow / Cantina'
        -- Referral / Partner
        when lower(utm_source) in (
            'spearbit.com', 'theblock.co', 'morpho.org', 'github.com', 'medium.com',
            'ethereum.org', 'lu.ma', 'luma.com', 'blog.lido.fi', 'docs.ethena.fi',
            'docs.megapot.io', 'docs.size.credit', 'eggs-finance.gitbook.io',
            'hub.forum.berachain.com', 'uniswapfoundation.org', 'solaxy.io'
        ) then 'Referral / Partner'
        -- Press / Media
        when lower(utm_source) in (
            'cloudseclist', 'companionlink.com', 'techbullion.com',
            'onlinethreatalerts.com', 'eqchi.r.ag.d.sendibm3.com'
        ) then 'Press / Media'
        -- Direct
        when lower(utm_source) = 'direct' then 'Direct'
        -- Organic (unspecified)
        when lower(utm_source) = 'organic' then 'Organic (unspecified)'
        -- Referral (generic)
        when lower(utm_source) = 'referral' then 'Referral / Partner'
        -- Anything else not in the taxonomy → Unknown (corrupted UTM)
        else 'Unknown (corrupted UTM)'
    end as channel,
    case
        when utm_source = 'utm_medium:' then 'corrupted'
        when utm_source is null or utm_source = '' then 'missing'
        else 'clean'
    end as utm_quality
from contacts
