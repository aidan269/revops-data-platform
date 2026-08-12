-- Current automation assets across all evidence sources.
-- Evidence only: no row here authorizes an external write.
select
    a.asset_id, a.source_system, a.native_id, a.name, a.asset_type, a.object_type,
    a.state, a.owner_identity, a.evidence_state, a.last_observed,
    s.collection_status, s.baseline_established, s.collector, s.source_artifact,
    false as authorizes_external_write
from {{ source('raw', 'automation_assets') }} a
join {{ source('raw', 'automation_source_snapshots') }} s on s.snapshot_id = a.snapshot_id
where a.last_seen_load = (select max(load_id) from {{ source('raw', 'automation_loads') }})


-- Current state = entities seen by the most recent load. History is retained;
-- entities that stopped appearing keep an older last_seen_load and drop out here.
