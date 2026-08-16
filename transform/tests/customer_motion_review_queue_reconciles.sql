-- Every unclassified detail record must appear exactly once in the queue.
with detail as (
    select deal_id
    from {{ ref('fct_customer_motion_live') }}
    where customer_motion = 'unclassified'
),
queue as (
    select deal_id from {{ ref('mart_customer_motion_review_queue_live') }}
)
select coalesce(detail.deal_id, queue.deal_id) as deal_id
from detail
full outer join queue using (deal_id)
where detail.deal_id is null or queue.deal_id is null
