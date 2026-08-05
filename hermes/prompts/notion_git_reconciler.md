# Job: Notion ↔ Git reconciler (merge-on-signoff + drift check)

**Goal:** keep the Notion Tasks board and GitHub in agreement, in one direction — the human acts
in Notion, git is made to match — and alarm loudly on any drift. **Surface, don't paper over.**

Runs on a schedule (e.g. every 15–30 min, or daily) with a GitHub token scoped to this repo
(Contents + Pull requests: write) and access to the 🏊 Tasks database.

## What it does each run

1. **Merge on sign-off.** For every task card whose **Status = Signed Off** and whose **PR** is
   open: merge that PR into `main` (squash), then set the card **Status → Done**. Idempotent —
   a card already Done, or a PR already merged, is skipped.
2. **Reflect merges back.** For every PR merged outside this job (e.g. a human clicked Merge):
   set the matching card to **Done** if it isn't already.
3. **Drift check (the integrity guard).** Flag and report — never auto-resolve — any of:
   - Card = **Signed Off** but its **PR** is closed-unmerged or missing → *approval with nowhere to land.*
   - PR **merged** but card is **not** Done / Signed Off → *code shipped without a recorded approval.*
   - Card = **Needs Review** but **PR**/**Branch** empty → *asked for review with nothing to review.*
   - Branch exists with commits ahead of `main` but **no PR** → *unpushed/untracked work.*

## Guardrails

- **One direction only.** The human edits Notion status; this job edits git (merges) and stamps
  `Done`. It must **never** move a card *into* `Signed Off` — that approval is a human's alone.
- **Never force-merge.** If a PR has conflicts or failing checks, do not merge — report it as drift.
- **Report** the drift list to the same channel as the data-quality monitor. Each line:
  task · card status · PR state · what's wrong.
