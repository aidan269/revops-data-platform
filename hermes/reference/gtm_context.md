# GTM context & moat (canonical) — Cantina

Grounding for every GTM-intelligence task Gerald runs. Keeps strategic answers tied to what we actually sell and to first-party truth, not opinion. Cite the table/column behind every number.

## What we sell (from cantina.security, Aug 2026)

Agentic security platform. Clarion (shared-context agentic platform + decision logging), Apex (agentic offensive-security engineer — exploit discovery → fix), Bug Bounty (noise-canceling, dedupes/validates reports).

Positioning: "the security workforce behind your security workforce" — lean teams get the coverage of a security org 10x their size. Closes the loop from discovery to verified fix ("open loops become breaches"). ~2–5 min typical time to remediation; every decision auditable.

Stated ICP: CISOs & security leaders, lean security teams, mid-to-large enterprises with complex/ sprawling security stacks and tool/team fragmentation.

Proof points (marquee logos): Anthropic, NVIDIA, Salesforce, Apple, Coinbase, GitLab, Nord Security, SAP, Spring. ~$16.5M Series funding.

Messaging themes to test against win data: "workforce behind your workforce"; "close every loop / discovery → verified fix"; "coverage 10x your size"; "signal in, fixes out"; "2–5 min to remediation"; the "71% of incidents become breaches (up from 32% in 2023)" threat stat.

## The moat (what we are building)

An AI-native company's GTM moat is not a campaign or a slogan — it's a compounding loop on proprietary first-party data: our CRM + warehouse + campaign/engagement (and later product & bug-bounty/community signals), with Gerald continuously turning them into GTM decisions faster and more precisely than a competitor can replicate. It compounds because (a) the data is ours alone, (b) the loop is closed — decision → action → measured → learned — and (c) it's auditable. It is the exact thesis Cantina sells to customers, applied to our own go-to-market.

## What makes a GTM answer trustworthy here (guardrails)

- **Deterministic-first.** Every GTM metric is a dbt model / SQL on the warehouse, not a vibe.
- **Ground truth = won deals.** ICP / segment / motion conclusions derive from `hs_is_closed_won` (the authoritative ~1,885), never from stage labels or opinion. Reconcile.
- **Model only for fuzzy grouping** (account clustering, messaging themes) — never to invent a fact, a customer, or a number. Raw data is always preserved behind any label.
- **External / competitive inputs** must be sourced and dated, and kept separate from first-party truth.
- **Enrichment is the ceiling.** ICP precision is capped by firmographic coverage (today: seniority ~1.4%, industry ~68%). Every ICP claim carries its coverage caveat; enrichment tasks feed this layer.
- **Read-only for analysis.** Any CRM writeback (e.g. writing an account fit-score) still goes through the guarded writer, whitelist, and human approval.

## The GTM question set (each becomes a Gerald task)

1. **ICP precision** — what does our best / fastest / biggest win actually look like, and does our pipeline resemble it? → Task 6.
2. **Winning motion** — which segment × channel × message combinations produce pipeline → won, and how do we manufacture more of the winning one (e.g. Referral/Partner)? → Task 7.
3. **Message–market resonance** — which positioning themes land with which ICP segment? → Task 8.
4. **Account prioritization** — score inbound + target accounts by fit + engagement; surface the next-best accounts to work. → Task 9.
5. **Pipeline leak & forecast** — where does pipeline stall by stage/segment, and what is likely to close this quarter? → Task 10.
