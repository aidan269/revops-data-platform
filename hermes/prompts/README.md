# Hermes prompts

Version-controlled prompts, improved like code — not tweaked in a UI.

## How they compose

- **`system.md`** is always loaded as Hermes's system prompt (role + guardrails).
- Each **job file** (`crm_enrichment.md`, `attribution_debugging.md`,
  `data_quality_monitor.md`) is loaded on top as the task instruction for that run.

So a run = `system.md` + one job file. The system prompt sets the rules once; the job file
says what to do this time.

## Loading into Hermes

1. Point Hermes's **system prompt** at `system.md`.
2. For a given run, pass the relevant **job file** as the task/instruction.
3. Keep everything in **git**. Change prompts via commits/PRs so you can review, diff, and
   roll back like code. Don't edit them live in the agent UI.

## Adding a job

Copy an existing job file, keep the same shape (**Goal → Steps → Guardrails**), commit it.
Small, single-purpose prompts beat one giant one — easier to test and improve.

## The guardrail that matters most

Deterministic first, controlled writes only. The local model is for fuzzy classification
(e.g. title → seniority), never for inventing facts or free-writing HubSpot fields.
