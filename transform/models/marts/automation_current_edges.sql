-- Dependency edges with endpoint resolution preserved.
select
    e.edge_id, e.asset_id, a.source_system, a.name as asset_name, a.state as asset_state,
    e.source_node_id, e.target_node_id, e.source_ref, e.target_ref,
    e.path_type, e.basis, e.endpoints_resolved, e.evidence_reference,
    false as authorizes_external_write
from {{ source('raw', 'automation_edges') }} e
join {{ source('raw', 'automation_assets') }} a on a.asset_id = e.asset_id
where e.last_seen_load = (select max(load_id) from {{ source('raw', 'automation_loads') }})


-- Current state = entities seen by the most recent load. History is retained;
-- entities that stopped appearing keep an older last_seen_load and drop out here.
