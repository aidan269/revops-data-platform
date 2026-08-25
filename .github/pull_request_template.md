### What changed (plain English)
<!-- What a reviewer needs to understand the change without reading the diff. -->

### Verification

- `pytest tests/ -q`:
- Migrations applied and re-run clean (checksum skip):

### Read-only boundary

- [ ] No non-GET HubSpot call added; no CRM record created, updated, archived, or deleted
- [ ] Raw tables remain append-only (no UPDATE/DELETE/TRUNCATE of landed history)
- [ ] No write-back, transformation, or agent module reintroduced
- [ ] No assertion weakened and no guardrail loosened

**A PR approval approves code.** It does not authorize any CRM mutation.

### Merge rules

1. **Never merge with red CI.** A green signal has to mean something or it means nothing.
2. **Before merging, state what you checked.** Reading your own diff and writing down what
   you verified is the minimum bar when merging alone.
3. **A second approving review is required when someone is available**, and unconditionally
   for changes touching `db/` migrations or `.github/workflows/`.
