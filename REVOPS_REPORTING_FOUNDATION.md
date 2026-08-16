# RevOps reporting foundation

`mart_pipeline_health_live` is the canonical current-state pipeline report.
It uses the HubSpot pipeline API to map internal stage IDs to the names used by
the operating team, and it limits records to the live-deal population.

The report exposes, per stage:

- deal count and pipeline amount;
- missing Deal Source coverage;
- missing company association coverage;
- missing primary-contact coverage.

This is reporting and data governance only. It does not change a deal, stage,
pipeline, property, or sales workflow.
