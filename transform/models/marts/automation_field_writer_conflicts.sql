-- Protected-field writers and overlapping-writer conflicts.
with writers as (
    select fa.system, fa.object_type, fa.property_name, fa.asset_id,
           a.name as asset_name, a.state, fa.overwrite_behavior, fa.basis, fa.confidence
    from {{ source('raw', 'automation_field_access') }} fa
    join {{ source('raw', 'automation_assets') }} a on a.asset_id = fa.asset_id
    where fa.operation in ('write', 'create', 'clear')
      and fa.last_seen_load = (select max(load_id) from {{ source('raw', 'automation_loads') }})
),
agg as (
    select system, object_type, property_name,
           count(distinct asset_id) as writer_count,
           count(distinct case when state = 'active' then asset_id end) as active_writer_count
    from writers group by 1, 2, 3
)
select w.*, g.writer_count, g.active_writer_count,
       lower(w.property_name) in
         ('primary_campaign_source','latest_campaign_source','deal_source','repo_uri') as is_protected_field,
       g.active_writer_count > 1 as has_overlapping_active_writers,
       false as authorizes_external_write
from writers w
join agg g on g.system = w.system and g.object_type = w.object_type
          and g.property_name = w.property_name
