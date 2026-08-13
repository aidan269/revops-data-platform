"""Runtime locations for the automation digital twin.

Nothing here hardcodes a developer's filesystem. Every location resolves from an
environment variable first, then a repository-relative default.

  REVOPS_ARTIFACT_ROOT   evidence/artifact root      (default: <repo>/hermes_shared/artifacts)
  REVOPS_LEDGER_PATH     audit ledger JSONL          (default: <repo>/hermes_shared/ledger/execution_events.jsonl)
  REVOPS_CHECKPOINT_PATH simulator checkpoint dir    (default: <repo>/.automation_twin_checkpoints)
  DATABASE_URL           warehouse connection        (no default; must be supplied explicitly)
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def artifact_root() -> Path:
    return Path(os.getenv("REVOPS_ARTIFACT_ROOT", REPO_ROOT / "hermes_shared" / "artifacts"))


def ledger_path() -> Path:
    return Path(os.getenv("REVOPS_LEDGER_PATH",
                          REPO_ROOT / "hermes_shared" / "ledger" / "execution_events.jsonl"))


def checkpoint_path() -> Path:
    return Path(os.getenv("REVOPS_CHECKPOINT_PATH", REPO_ROOT / ".automation_twin_checkpoints"))


def database_url() -> str | None:
    """No default. A warehouse URL must be supplied explicitly."""
    return os.getenv("DATABASE_URL")
