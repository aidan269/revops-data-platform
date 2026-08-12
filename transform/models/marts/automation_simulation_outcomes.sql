-- Simulation outcomes. Simulated runs are never conflated with observed executions.
select
    run_id, asset_id, run_kind, fixture_name, input_fixture_hash, result,
    jsonb_array_length(proposed_writes) as proposed_write_count,
    jsonb_array_length(blocked_writes)  as blocked_write_count,
    jsonb_array_length(findings)        as finding_count,
    executed_externally, created_at,
    false as authorizes_external_write
from {{ source('raw', 'automation_runs') }}
