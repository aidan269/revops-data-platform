### What changed (plain English)
<!-- What a reviewer needs to understand the change without reading the diff. -->

### Verification evidence
<!-- Test counts, and reconciliations to known truths (closed-won ≈1,885, corrupted-UTM = 138). -->

- CI portable suite:
- CI migrations / safety invariants:
- Evidence-dependent suites run locally with evidence present? (CI only runs the portable
  subset — ~85 tests are invisible to it. State whether you ran them and the result, or
  "not run" so it's recorded rather than assumed.)

### Guardrail status
<!-- Read-only, or a proposal was generated? -->

- [ ] Read-only — no HubSpot/Apollo/Zapier mutation, no proposal generated
- [ ] A proposal was generated and handed to the coordinator (dry-run only)
- [ ] No assertion weakened, no guardrail loosened, no evidence file committed

**A PR approval approves code.** It does not authorize any CRM mutation. That requires a
separate approval naming the exact proposal and target population, given to the coordinator
per `hermes_shared/HANDOFF_PROTOCOL.md` step 3.

### 👉 What to eyeball
<!-- Write this so a non-developer can do it in two minutes. -->

---

### Merge rules

1. **Never merge with red CI.** A green signal has to mean something or it means nothing.
2. **Before merging, post your answers to "what to eyeball" as a comment.** Reading your own
   diff and writing down what you checked is the minimum bar when merging alone.
3. **A second approving review is required when someone is available**, and is required
   unconditionally — no solo merge — for changes touching:
   - `writeback/`
   - the approval boundary: `automation_twin/simulator.py`, `hermes_shared/execution_events.py`
   - `db/` migrations
   - `.github/workflows/`
4. **Otherwise self-merge is permitted** once 1–3 are satisfied.
