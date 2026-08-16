# APOLLO-INFRA-BASELINE

Read-only. Six read tools called, **zero write tools**. No Apollo or HubSpot
record, setting, mapping, sequence, integration or permission was created,
edited, activated, retried or saved. `execution_authorized: false`.

## Headline: the MCP cannot baseline the integration

The authenticated Apollo MCP exposes **62 tools, overwhelmingly write-oriented**
(create / update / bulk_create / send_now / approve / enrich). What it does *not*
expose is decisive:

> **no imports, no exports, no integration settings, no field mappings, no sync
> rules, no error logs, no workflows, no enrichment schedules, no user directory,
> no workspace name, no plan.**

It is a sales-engagement API, not an admin API. **Four of the ten required
sections — users, import history, HubSpot integration, error logs — are
`NOT_COLLECTED`.** Their artifacts carry a single explanatory row each. A zero-row
inventory here means *inaccessible*, never *absent*.

## Workspace verdict: populated, name unverified

No MCP surface returns a workspace name, so "Spearbit Labs" could be neither
confirmed nor refuted **by name**. The evidence available:

| Signal | Reading |
|---|---|
| `team_id` `6a04fc8ce0409a001dd5728f` | the only stable workspace identifier exposed |
| 97 lists, 9,023 cached records, incl. Black Hat + healthcare | **inconsistent** with the separate *empty* Cantina workspace |
| Context Center: domain `cantina.security`, name "Cantina" | a branding profile, not a workspace name |
| Legacy `@spearbit.com` identities own the assets | consistent with the historical Spearbit workspace |

I did **not** trigger the stop condition. The resolved workspace is demonstrably
the populated historical one; only its label is unverified. Future baselines
should key on `team_id`, not the name.

Current identity **matches expectation**: `aidan@cantina.security`
(`6a50179f6cd7ec0020057064`). **Role is not exposed** — Admin is unverified.

## What was collected

| Surface | Result |
|---|---|
| Lists | 97 (77 contact / 20 account), 9,023 cached records |
| Sequences | 9 — **all inactive, zero sends ever** |
| Email accounts | 1 — `mohammad@spearbit.com`, active, default |
| Custom contact fields | 1 — `Qualify Contact`, readonly picklist |
| Context Center | 4 products, approved, owner id unresolved |
| Credits | 0 used of every type |

## Attribution contamination

| Suspected writer | Classification |
|---|---|
| Apollo | **CORROBORATED** (as origin, not as writer) |
| Apollo continuous CRM sync | NOT_EVALUABLE |
| Apollo sequences | **NOT_SUPPORTED** |
| Apollo custom fields | **NOT_SUPPORTED** |
| Findymail, LeadMagic, User Managed, Prospeo, Icypeas | NOT_EVALUABLE |

**Observed:** Apollo holds lists named `AutomationAnywhere`, `Cresta`, `Decagon`,
`Writer.com`, `Observe.AI`, `Appzen`, `Skit.ai` — the same names as HubSpot import
source files. Counts differ in six of seven pairs (Apollo 31 vs HubSpot 26; 12/11;
16/15; 9/7; 6/4; 3/2; Cresta 20/20 matches).

**Inference, held separately:** this fits Apollo lists being exported to CSV and
imported into HubSpot as a separate act — not a live sync. Name correspondence
with differing counts is corroboration, **not** proof that any specific Apollo
list produced any specific HubSpot import. Per the control, similarly named Black
Hat files were **not** treated as equivalent; no Apollo-side identifier was
available to match `blackhatrayhan.csv`, `blackhat2` or `bhf.csv` to anything.

Two things Apollo is now **excluded** as: sequences (never executed) and custom
fields (none resembles a campaign source).

The strongest signal against "Apollo wrote it" remains from CRM-017: the single
source `blackhat2` carries **five different vendor values**. One integration does
not write five competitors' names — an email-provenance spreadsheet column does.

## Recurrence risk

- **Default enrichment settings: NOT_EVALUABLE.** No surface; the browser-reported
  warning could not be verified.
- **CSV export→import path: ACTIVE.** Apollo remains the origin of list-building
  exports, but the risk lives in the **HubSpot import mapping**, not in Apollo.
  Fixing Apollo would not close it.

## Five safest proposed remediations — none executed

1. **Import-template control** — a standard HubSpot import mapping that can never
   map a vendor/provenance column to `Primary Campaign Source`. Addresses the only
   corroborated path.
2. **Dedicated enrichment-provenance property** — send vendor labels to
   `Lead Data Provider`, keeping `Primary Campaign Source` for campaign attribution.
3. **Protect `Primary Campaign Source`** — restrict who and what may write it, so
   an import cannot silently overwrite attribution.
4. **Legacy identity plan** — assets and CRM auth depend on `@spearbit.com`
   accounts. Enumerate all users in the browser *before* any change; reauthenticating
   under `aidan@cantina.security` is appropriate but must follow, not precede, that
   inventory. Do not disconnect anything first.
5. **Exact-record validation cohort** — the 14 evidence-supported CRM-017 contacts,
   kept strictly separate. **No bulk cleanup of the 1,577 without recoverable
   evidence.** Any repair needs exact record IDs, fields, old and new values, and
   its own approval.

## Limitations

Everything about the HubSpot integration itself — portal ID, auth identity, sync
direction, mappings, conflict rules, enrichment settings, last-sync state and the
2026-06-30 `Push Contacts / CRM Unlinked` failure — remains browser-only. That
failure is worth noting: a *push* implies a write path distinct from CSV import,
which this baseline could neither confirm nor size. It was not retried.
