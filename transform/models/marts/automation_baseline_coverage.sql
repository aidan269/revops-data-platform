-- Coverage by system. A NOT_COLLECTED surface can never read as a healthy baseline.
select
    source_system,
    count(*) as snapshots,
    count(*) filter (where collection_status = 'COLLECTED')     as collected,
    count(*) filter (where collection_status = 'PARTIAL')       as partial,
    count(*) filter (where collection_status = 'NOT_COLLECTED') as not_collected,
    bool_or(baseline_established) as any_baseline_established,
    count(*) filter (where collection_status = 'NOT_COLLECTED' and baseline_established)
        as dishonest_baselines,
    false as authorizes_external_write
from {{ source('raw', 'automation_source_snapshots') }}
where last_seen_load = (select max(load_id) from {{ source('raw', 'automation_loads') }})
group by 1


-- Current state = entities seen by the most recent load. History is retained;
-- entities that stopped appearing keep an older last_seen_load and drop out here.
