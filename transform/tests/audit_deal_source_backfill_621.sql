-- Preserve the known reconstructed backfill population.
select count(*) as actual_count
from {{ ref('mart_deal_source_backfill_audit') }}
having count(*) != 621
