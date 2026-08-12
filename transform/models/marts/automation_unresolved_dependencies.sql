-- Everything the twin knows it cannot see. Never presented as healthy.
select 'uncollected_surface' as gap_type, s.source_system, s.source_artifact as reference,
       s.collection_status as detail, s.not_collected_reason as reason,
       s.baseline_established, false as authorizes_external_write
from {{ source('raw', 'automation_source_snapshots') }} s
where s.collection_status <> 'COLLECTED'
  and s.last_seen_load = (select max(load_id) from {{ source('raw', 'automation_loads') }})
union all
select 'unresolved_edge', a.source_system, e.edge_id,
       coalesce(e.source_ref, '?') || ' -> ' || coalesce(e.target_ref, '?'),
       e.evidence_reference, false, false
from {{ source('raw', 'automation_edges') }} e
join {{ source('raw', 'automation_assets') }} a on a.asset_id = e.asset_id
where e.endpoints_resolved = false
  and e.last_seen_load = (select max(load_id) from {{ source('raw', 'automation_loads') }})
