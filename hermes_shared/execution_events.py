#!/usr/bin/env python3
"""Append-only lifecycle event writer for the Hermes shared audit feed.

This module is coordinator infrastructure. It is intentionally not registered
as an MCP tool and has no CRM, browser, shell, or database capability.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_EVENT_PATH = Path(__file__).resolve().parent / "ledger" / "execution_events.jsonl"
REQUIRED_FIELDS = {
    "timestamp", "proposal_id", "item_type", "item_id", "action", "status",
    "evidence_reference", "message",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,120}$")
TOKEN_PATTERN = re.compile(
    r"(?i)(authorization\s*:\s*bearer|private[_ -]?app[_ -]?token\s*[:=]|api[_ -]?key\s*[:=]|password\s*=)"
)
MAX_MESSAGE_LENGTH = 500
MAX_REFERENCE_LENGTH = 500


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _single_line(value: str, field: str, maximum: int) -> str:
    normalized = " ".join(str(value).split())
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters")
    if TOKEN_PATTERN.search(normalized):
        raise ValueError(f"{field} appears to contain a credential or secret")
    return normalized


def validate_event(event: dict[str, Any]) -> dict[str, str]:
    """Return a normalized event or reject unsafe/incomplete input."""
    missing = REQUIRED_FIELDS - set(event)
    extra = set(event) - REQUIRED_FIELDS
    if missing:
        raise ValueError(f"missing required event fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"unsupported event fields: {', '.join(sorted(extra))}")
    normalized = {key: str(event[key]) for key in REQUIRED_FIELDS}
    for field in ("proposal_id", "item_type", "item_id", "action", "status"):
        if not ID_PATTERN.fullmatch(normalized[field]):
            raise ValueError(f"{field} must be a safe identifier")
    normalized["timestamp"] = _single_line(normalized["timestamp"], "timestamp", 40)
    try:
        datetime.fromisoformat(normalized["timestamp"].replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("timestamp must be ISO-8601") from error
    normalized["evidence_reference"] = _single_line(normalized["evidence_reference"], "evidence_reference", MAX_REFERENCE_LENGTH)
    normalized["message"] = _single_line(normalized["message"], "message", MAX_MESSAGE_LENGTH)
    return {field: normalized[field] for field in (
        "timestamp", "proposal_id", "item_type", "item_id", "action", "status",
        "evidence_reference", "message",
    )}


def append_execution_event(
    *, proposal_id: str, item_type: str, item_id: str, action: str, status: str,
    evidence_reference: str, message: str, event_path: Path = DEFAULT_EVENT_PATH,
    timestamp: str | None = None,
) -> dict[str, str]:
    """Atomically append one validated JSON line and return the stored event."""
    event = validate_event({
        "timestamp": timestamp or _utc_timestamp(), "proposal_id": proposal_id,
        "item_type": item_type, "item_id": item_id, "action": action,
        "status": status, "evidence_reference": evidence_reference, "message": message,
    })
    event_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(event_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError("incomplete audit event append")
        os.fsync(descriptor)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    return event
