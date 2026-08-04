"""
Raw lead landing-zone ingestion endpoint (v1 prototype).

Point every HubSpot form / Make webhook at POST /ingest. This writes the FULL
raw payload append-only BEFORE any field mapping. Downstream mapping reads FROM
this table; if a mapping bug ships, you replay from raw instead of losing data.

Run locally:  uvicorn ingest:app --reload
Test:         curl -X POST localhost:8000/ingest -d 'utm_source=google&utm_medium=cpc&email=a@b.com'
"""
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request

app = FastAPI(title="Lead Landing Zone")

# Swap this for a Snowflake/Postgres writer in prod. Local JSONL keeps the
# prototype runnable with zero infra.
LANDING_FILE = os.getenv("LANDING_FILE", "leads_raw.jsonl")


def record_hash(payload: dict) -> str:
    """Stable hash of the normalized payload for dedupe / idempotency."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()


@app.post("/ingest")
async def ingest(request: Request):
    ctype = request.headers.get("content-type", "")
    if ctype.startswith("application/x-www-form-urlencoded") or ctype.startswith("multipart/form-data"):
        payload = dict(await request.form())
    else:
        payload = await request.json()

    row = {
        "event_id":   payload.get("event_id") or str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source":     payload.get("source") or request.query_params.get("source"),
        "form_id":    payload.get("form_id") or payload.get("hs_form_guid"),
        "raw_payload": payload,               # the whole thing, untouched
        "record_hash": record_hash(payload),
        "status":     "raw",
    }

    # Append-only. Dedupe on record_hash at read time.
    with open(LANDING_FILE, "a") as f:
        f.write(json.dumps(row) + "\n")

    return {"ok": True, "event_id": row["event_id"]}
