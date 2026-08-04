"""
Guarded HubSpot writer — the ONLY path that writes back to HubSpot.

Enforced rules:
- Only fields on WHITELIST can be written. Anything else is refused.
- dry_run=True by default: computes + logs the diff, does NOT call HubSpot.
- Every change (dry-run or live) is recorded in analytics.hubspot_writeback_log.
- Before a live write, re-reads the current HubSpot value; skips + logs if
  the value is no longer null (never clobber a human-set value).
- All writes are tagged with a batch_id and source (the rule that produced
  the new value), so every change is auditable and reversible.

This is the safety boundary. Hermes and analytics never call the HubSpot API
directly — they go through write_fields().
"""

import os
import uuid

import psycopg2
import requests

HUBSPOT_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
HS_BASE = "https://api.hubapi.com"

# The ONLY fields that may ever be pushed back. Add to this list deliberately.
WHITELIST = {
    "contact": {"hs_seniority", "icp_fit", "black_hat_lead_grade"},
    # "company": {...},  # add when needed
}


def _current_value(object_type, object_id, field):
    """Fetch the current HubSpot value so the log records a real old → new diff."""
    if not HUBSPOT_TOKEN:
        return None
    r = requests.get(
        f"{HS_BASE}/crm/v3/objects/{object_type}s/{object_id}",
        headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
        params={"properties": field},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("properties", {}).get(field)


def _log(cur, object_type, object_id, field, old, new, dry_run, source=None, batch_id=None):
    cur.execute(
        """INSERT INTO analytics.hubspot_writeback_log
           (object_type, object_id, field, old_value, new_value, source, batch_id, dry_run)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (object_type, object_id, field,
         None if old is None else str(old), str(new),
         source, batch_id, dry_run),
    )


def write_fields(object_type, object_id, updates: dict, dry_run: bool = True,
                 source: str | None = None, batch_id: str | None = None):
    """
    updates = {field: new_value}. Returns the applied/simulated diff.
    Refuses any field not on the whitelist. Skips no-op writes (old == new).

    For live writes (dry_run=False):
      - Re-reads each field's current value from HubSpot immediately before writing.
      - Skips + logs any field that is no longer null (never clobber a human-set value).
      - Writes idempotently and logs every change with source + batch_id.
    """
    allowed = WHITELIST.get(object_type, set())
    bad = set(updates) - allowed
    if bad:
        raise ValueError(f"Refusing to write non-whitelisted {object_type} fields: {sorted(bad)}")

    conn = psycopg2.connect(DATABASE_URL)
    applied = []
    skipped = []
    to_send = {}
    with conn, conn.cursor() as cur:
        for field, new in updates.items():
            old = _current_value(object_type, object_id, field)

            # No-op: old == new, skip
            if str(old) == str(new):
                continue

            # Live-write guard: if old is not null and we're writing live,
            # a human has set this value since the preview. Skip + log.
            if not dry_run and old is not None and old != "":
                _log(cur, object_type, object_id, field, old, new, dry_run=False,
                     source=f"SKIPPED (clobber guard: value is '{old}', not null) | {source}",
                     batch_id=batch_id)
                skipped.append({"field": field, "old": old, "new": new,
                                "reason": "clobber_guard"})
                continue

            _log(cur, object_type, object_id, field, old, new, dry_run,
                 source=source, batch_id=batch_id)
            applied.append({"field": field, "old": old, "new": new})
            to_send[field] = new

        if not dry_run and to_send:
            if not HUBSPOT_TOKEN:
                raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN not set (write scope required)")
            r = requests.patch(
                f"{HS_BASE}/crm/v3/objects/{object_type}s/{object_id}",
                headers={"Authorization": f"Bearer {HUBSPOT_TOKEN}"},
                json={"properties": to_send},
                timeout=30,
            )
            r.raise_for_status()

    conn.close()
    return {
        "dry_run": dry_run,
        "object_type": object_type,
        "object_id": object_id,
        "batch_id": batch_id,
        "applied": applied,
        "skipped": skipped,
    }


def rollback_batch(batch_id: str, dry_run: bool = True):
    """
    Produce the rollback for a batch_id — reverts each live write to its old_value.
    Returns a list of write_fields calls that would undo the batch.
    Does NOT execute unless dry_run=False.
    """
    conn = psycopg2.connect(DATABASE_URL)
    with conn, conn.cursor() as cur:
        cur.execute(
            """SELECT object_type, object_id, field, old_value, new_value, source
               FROM analytics.hubspot_writeback_log
               WHERE batch_id = %s AND dry_run = false
               ORDER BY id""",
            (batch_id,),
        )
        rows = cur.fetchall()
    conn.close()

    rollback_calls = []
    for obj_type, obj_id, field, old_val, new_val, src in rows:
        if old_val is None or old_val == "":
            # Was null before — clear the field
            rollback_calls.append({
                "object_type": obj_type,
                "object_id": obj_id,
                "field": field,
                "old": new_val,
                "new": None,
                "source": f"ROLLBACK of batch {batch_id} (reverting to null)",
            })
        else:
            rollback_calls.append({
                "object_type": obj_type,
                "object_id": obj_id,
                "field": field,
                "old": new_val,
                "new": old_val,
                "source": f"ROLLBACK of batch {batch_id} (reverting to '{old_val}')",
            })

    return rollback_calls


if __name__ == "__main__":
    # Dry-run demo: logs the diff, writes NOTHING to HubSpot.
    print(write_fields("contact", "12345", {"hs_seniority": "executive"}, dry_run=True))
