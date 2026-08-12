# AUTOMATION-DIGITAL-TWIN

A vendor-neutral automation graph, LangGraph simulator, and policy engine over
local Postgres. Read-only with respect to every external system.
`execution_authorized: false`.

## What it does

Connects the CRM-013 → CRM-020, BRAND-INBOUND-RECOVERY and APOLLO-INFRA-BASELINE
evidence into one canonical model — assets, nodes, edges, field access, runs,
findings, approvals — then simulates automation against synthetic fixtures and
reports what *would* happen.

It cannot mutate anything. That is structural, not a convention:

- No module imports a write-capable client; a test greps for them.
- `policy.assert_no_production_adapter()` fails if an executor module ever appears.
- The LangGraph approval interrupt is followed by a terminal `safe_stop` node.
  **There is nothing after the boundary to execute an approved write.**
- The CLI has no `execute` command, and forbidden verbs exit non-zero.
- Every evidence table carries `authorizes_external_write` pinned false by CHECK.
  Only `raw.automation_approvals` may ever hold true, and only with a named
  approver, a timestamp, and status `APPROVED`.

## Honesty guarantees

The hardest requirement was **not** faking completeness.

- A `NOT_COLLECTED` snapshot **cannot** claim a baseline — enforced in the
  dataclass, by a database CHECK, and by a dbt test asserting
  `dishonest_baselines = 0`.
- Known-but-uncollected assets become **stubs with no invented nodes or edges**.
  All five known Zaps are present; none has a single fabricated step.
- **There are zero nodes in the graph.** That is the correct result: no workflow
  or Zap internal definition has ever been collected, so none was invented.
- Observation and inference are separate columns everywhere, and every inferred
  edge carries an evidence reference.

## Coverage

| System | Collected | Partial | Not collected |
|---|---|---|---|
| forms | 1 | 0 | 0 |
| hubspot | 0 | 1 | 1 |
| apollo | 0 | 2 | 5 |
| zapier | 0 | 1 | 1 |
| warehouse | 1 | 0 | 0 |
| ledger | 1 | 0 | 0 |

131 assets, 6 edges, 7 field-access records, 11 findings, 0 nodes.

## Five safe fixes implemented

1. **Protected-field import guardrail** — a fail-closed validator rejecting any
   vendor, provider, provenance, filename or enrichment column mapped to a
   protected attribution field. It normalises labels but **never approves by
   resemblance**: an unrecognised column mapped to a protected field is rejected.
   Tests reproduce the Black Hat pattern exactly — one file, five vendor literals.
2. **Lead Data Provider contract** — a local, approval-ready property proposal.
   The property is **not created**.
3. **Protected-field writer registry** — only registered assets may write
   protected fields. **No Apollo asset is approved for Primary Campaign Source.**
4. **Ten dry-run fixtures** — valid propagation, vendor contamination, blank and
   populated destinations, multi-deal ambiguity, deal-before-submission, missing
   association, inactive owner, duplicate creator, unresolved Zap target. No PII;
   a test asserts it.
5. **Baseline completeness guard** — three independent layers preventing an
   inaccessible surface from reading as a healthy zero-count baseline.

## A correction the simulator forced

The first implementation checked protected-field writers *before* checking whether
the destination was already populated. That mislabelled a harmless no-op as a
writer conflict. Precedence was corrected: a populated destination under an
`only_if_empty` rule is a **skip**, and only rules that would actually write are
tested against the protected-field controls. A regression test now pins both
orderings, including that an overwriting rule still hits the writer check.

## Simulation results

Ten fixtures, ten runs, **zero external executions**. Three stop safely
(no target, ambiguous target, unresolved Zap). Vendor contamination is blocked as
`would_conflict` on both the unregistered writer and the vendor literal.
Populated destinations yield `would_skip`. An absent source value yields
`cannot_evaluate` rather than a guess.

## Highest-severity findings

- **P1** — an unidentified writer puts vendor values into `Primary Campaign
  Source` and is not in the writer registry (1,591 contacts, 1,577 via import).
- **P1** — two active workflows both write `requested_service` on DEAL.
- **P2** — five known Zaps reach HubSpot through edges whose endpoints cannot be
  resolved, because no Zap definition was ever collected.
- **P2** — three Apollo assets and the HubSpot integration authentication depend
  on legacy `@spearbit.com` identities.
- **P2** — the Apollo integration reports default, unreviewed sync settings whose
  content is not collectable.

## What this does not prove

Apollo is corroborated as an upstream data **origin**. It is **not** a confirmed
writer, and the twin refuses to record it as one — a test enforces that. Zapier is
never named as the overwrite cause. Automation-platform record creation remains
distinct from overwrite causation throughout.
