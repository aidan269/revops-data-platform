"""
Guarded HubSpot writer — the ONLY path that writes back to HubSpot.

Enforced rules:
- Only fields on WHITELIST can be written. Anything else is refused.
- dry_run=True by default: computes + logs the diff, does NOT call HubSpot.
- Every change (dry-run or live) is recorded in analytics.hubspot_writeback_log.

This is the safety boundary. Hermes and analytics never call the HubSpot API directly —
they go through write_fields().
"""
import os

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
    """Fetch the current HubSpot value so the log records a real old -> new diff."""
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


def _log(cur, object_type, object_id, field, old, new, dry_run):
    cur.execute(
        """INSERT INTO analytics.hubspot_writeback_log
           (object_type, object_id, field, old_value, new_value, dry_run)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (object_type, object_id, field, None if old is None else str(old), str(new), dry_run),
    )


def write_fields(object_type, object_id, updates: dict, dry_run: bool = True):
    """
    updates = {field: new_value}. Returns the applied/simulated diff.
    Refuses any field not on the whitelist. Skips no-op writes (old == new).
    """
    allowed = WHITELIST.get(object_type, set())
    bad = set(updates) - allowed
    if bad:
        raise ValueError(f"Refusing to write non-whitelisted {object_type} fields: {sorted(bad)}")

    conn = psycopg2.connect(DATABASE_URL)
    applied = []
    to_send = {}
    with conn, conn.cursor() as cur:
        for field, new in updates.items():
            old = _current_value(object_type, object_id, field)
            if str(old) == str(new):
                continue  # no-op, don't write or log noise
            _log(cur, object_type, object_id, field, old, new, dry_run)
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
    return {"dry_run": dry_run, "object_type": object_type, "object_id": object_id, "applied": applied}


if __name__ == "__main__":
    # Dry-run demo: logs the diff, writes NOTHING to HubSpot.
    print(write_fields("contact", "12345", {"hs_seniority": "executive"}, dry_run=True))
