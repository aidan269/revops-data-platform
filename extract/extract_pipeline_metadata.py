#!/usr/bin/env python3
"""Extract HubSpot deal-pipeline metadata for reporting; never changes HubSpot."""

from __future__ import annotations

import json
import os

import psycopg2
import requests

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/warehouse")
HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
HS_BASE = "https://api.hubapi.com"

DDL = """
create table if not exists raw.hubspot_deal_stages (
    pipeline_id text not null,
    pipeline_label text,
    stage_id text not null,
    stage_label text,
    display_order integer,
    probability numeric,
    is_closed boolean,
    raw_metadata jsonb not null default '{}'::jsonb,
    extracted_at timestamptz not null default now()
)
"""


def main():
    if not HUBSPOT_TOKEN:
        raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN is not set in this Terminal window.")
    response = requests.get(
        f"{HS_BASE}/crm/v3/pipelines/deals",
        headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
        timeout=30,
    )
    response.raise_for_status()

    rows = []
    for pipeline in response.json().get("results", []):
        for stage in pipeline.get("stages", []):
            metadata = stage.get("metadata", {})
            probability = metadata.get("probability")
            rows.append((
                str(pipeline["id"]), pipeline.get("label"), str(stage["id"]),
                stage.get("label"), stage.get("displayOrder"),
                float(probability) if probability not in (None, "") else None,
                str(metadata.get("isClosed", "false")).lower() == "true",
                json.dumps(stage),
            ))

    with psycopg2.connect(DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(DDL)
        cur.executemany(
            """insert into raw.hubspot_deal_stages
               (pipeline_id, pipeline_label, stage_id, stage_label, display_order,
                probability, is_closed, raw_metadata)
               values (%s, %s, %s, %s, %s, %s, %s, %s)""",
            rows,
        )
    print(f"Extracted: {len(rows)} deal stages across {len(response.json().get('results', []))} pipelines")


if __name__ == "__main__":
    main()
