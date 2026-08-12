-- Latest stage metadata per pipeline/stage, from HubSpot's pipeline API.

with ranked as (
    select
        pipeline_id,
        pipeline_label,
        stage_id,
        stage_label,
        display_order,
        probability,
        is_closed,
        extracted_at,
        row_number() over (
            partition by pipeline_id, stage_id
            order by extracted_at desc
        ) as rn
    from {{ source('raw', 'hubspot_deal_stages') }}
)

select * from ranked where rn = 1
