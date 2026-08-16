#!/usr/bin/env python3
"""
Hermes MCP bridge for Codex.

An MCP (Model-Context Protocol) stdio server named ``hermes`` that exposes
a small, safe surface of local-LLM reasoning + status tools to Codex
(via the ``mcp`` Python package's FastMCP stdio transport).

Design rules
------------
* stdio transport only — never opens a network port.
* NO shell execution, NO arbitrary SQL, NO HubSpot writes,
  NO environment-variable dumping, NO file writes.
* Any future HubSpot-related tool MUST be proposal-only and dry-run.
* The local model is used for *reasoning / structured analysis* over
  read-only warehouse facts — never to invent facts.

Tools
-----
``hermes_reason``
    Send a task + optional context to the local Ollama chat API
    (``http://localhost:11434/api/chat``) and return structured JSON:
    summary, reasoning, recommendations, risks, follow_up_questions.

``hermes_job_status``
    Read-only inspection of background jobs / Docker services /
    dbt run artifacts.  Returns structured status with no side-effects.

Configuration
-------------
``HERMES_OLLAMA_MODEL``  (env)  Model name to call via Ollama chat API.
                                Defaults to ``llama3.1`` (the model this
                                project already uses for fuzzy
                                classification).
``HERMES_OLLAMA_HOST``   (env)  Ollama chat endpoint.
                                Defaults to ``http://localhost:11434/api/chat``.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import subprocess
from typing import Any

import urllib.error
import urllib.request

from mcp.server.fastmcp import FastMCP, Context

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

DEFAULT_MODEL = "llama3.1"          # project's default local classification model
DEFAULT_OLLAMA_HOST = "http://localhost:11434/api/chat"
DEFAULT_DOCKER_COMPOSE = "docker-compose.yml"
DEFAULT_DBT_TARGET = "transform"     # project-local dbt directory

OLLAMA_HOST = os.environ.get("HERMES_OLLAMA_HOST", DEFAULT_OLLAMA_HOST)
OLLAMA_MODEL = os.environ.get("HERMES_OLLAMA_MODEL", DEFAULT_MODEL)

# Maximum tokens to request from the model (keeps responses bounded).
MAX_TOKENS = int(os.environ.get("HERMES_MAX_TOKENS", "1024"))
# Per-request timeout (seconds) for the Ollama HTTP call.
REQUEST_TIMEOUT = float(os.environ.get("HERMES_OLLAMA_TIMEOUT", "60"))

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------- #
# MCP server
# --------------------------------------------------------------------------- #

mcp = FastMCP(
    name="hermes",
    # version is set via instructions; the MCP server reports it externally.
    instructions=(
        "Hermes is a RevOps data-platform agent (v0.1.0). It reasons over "
        "read-only warehouse/Git state and calls the local Ollama model "
        "(host network, never invents facts). "
        "No shell SQL, no HubSpot writes, no file writes, no env dumping."
    ),
)

# --------------------------------------------------------------------------- #
# Ollama client
# --------------------------------------------------------------------------- #


async def call_ollama(
    task: str,
    context: str | None,
    ctx: Context,
) -> dict[str, Any]:
    """Send ``task`` (+ optional ``context``) to the local Ollama chat API.

    Returns the raw parsed JSON response from Ollama.
    Raises ``RuntimeError`` with a clear message if the model or host is
    unreachable, so the MCP layer can surface the error to the caller.
    """
    model = OLLAMA_MODEL

    system_msg = (
        "You are Hermes, a RevOps data-platform agent. "
        "Reason deterministically from the facts provided. "
        "When you cannot be certain, say so and flag the risk. "
        "Never fabricate data or numbers. "
        "Return a response that contains: a one-sentence summary, "
        "a concise reasoning chain, actionable recommendations, "
        "notable risks or assumptions, and a short list of follow-up "
        "questions. Use plain English; do not invent metrics."
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": system_msg}]
    if context:
        messages.append({"role": "user", "content": f"Context:\n\n{context}"})
    messages.append({"role": "user", "content": f"Task:\n\n{task}"})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": MAX_TOKENS, "temperature": 0.2},
    }).encode()

    await ctx.info(f"Calling Ollama chat API at {OLLAMA_HOST} with model={model}")

    loop = asyncio.get_event_loop()
    def _do() -> dict[str, Any]:
        req = urllib.request.Request(
            OLLAMA_HOST,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            # HTTPError is a subclass of URLError, so catch it first for a
            # more specific message (e.g. 404 when the model is not pulled).
            raise RuntimeError(
                f"Ollama returned HTTP {exc.code} for model '{model}'. "
                f"Pull it with:  ollama pull {model}   "
                f"(Body: {exc.read().decode()[:200]})"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama is unreachable at {OLLAMA_HOST} (is `ollama serve` "
                f"running with a native host install?). Underlying error: {exc}"
            ) from exc
    return await loop.run_in_executor(None, _do)


def parse_structured(content: str) -> dict[str, Any]:
    """Parse an LLM text response into structured fields.

    The model is prompted to return a JSON object; this helper
    tolerantly extracts it (stripping ``\\`\\`\\`json`` fences) and falls
    back to plain-text field extraction if JSON parsing fails.
    """
    text = content.strip()

    # Try to extract a ```json ... ``` block.
    if "```json" in text or "```" in text:
        start = text.find("```json")
        if start == -1:
            start = text.find("```")
        end = text.find("```", start + 3)
        if start != -1 and end != -1:
            candidate = text[start + 3:end].strip()
        else:
            candidate = text
    else:
        candidate = text

    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return _normalize(obj)
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: regex extraction of labelled fields
    fields: dict[str, Any] = {}
    for key in ("summary", "reasoning", "recommendations", "risks", "follow_up_questions"):
        val = _extract_field(text, key)
        if val:
            fields[key] = val
    if not any(fields.values()):
        # Last resort — put the whole text in summary
        fields = {"summary": text, "reasoning": "", "recommendations": [],
                  "risks": [], "follow_up_questions": []}
    return _normalize(fields)


def _normalize(obj: dict[str, Any]) -> dict[str, Any]:
    """Ensure all expected keys exist with the right types."""
    return {
        "summary": str(obj.get("summary", "")).strip() or "",
        "reasoning": str(obj.get("reasoning", "")).strip() or "",
        "recommendations": _as_list(obj.get("recommendations", [])),
        "risks": _as_list(obj.get("risks", [])),
        "follow_up_questions": _as_list(obj.get("follow_up_questions", [])),
    }


def _as_list(v: Any) -> list[str]:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [l.strip() for l in v.splitlines() if l.strip()]
    if isinstance(v, dict):
        return [f"{k}: {v}" for k, v in v.items()]
    return []


def _parse_yaml(text: str) -> dict[str, Any]:
    """Parse YAML using ``yaml`` if available; fall back to a simple parser.

    The project's ``.venv`` may not include PyYAML (it lives in the dbt
    venv), so we degrade gracefully instead of hard-failing the tool.
    """
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        # Minimal fallback: not full YAML, but sufficient for profiles.yml
        # structure (key: value with 2-space indentation).
        result: dict[str, Any] = {}
        stack: list[tuple[int, Any]] = [(0, result)]
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            # Pop stack to the right nesting level
            while stack and indent < stack[-1][0]:
                stack.pop()
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val:
                    if val.lower() in ("true", "false"):
                        val = val.lower() == "true"
                    try:
                        val = int(val)
                    except ValueError:
                        pass
                    stack[-1][1][key] = val
                else:
                    new_dict: dict[str, Any] = {}
                    stack[-1][1][key] = new_dict
                    stack.append((indent, new_dict))
        return result


def _humanize_pg_setting(name: str, raw: str) -> str:
    """Convert raw PostgreSQL setting values to human-readable strings.

    Postgres stores memory settings as integers in units of 8KB pages
    (e.g. shared_buffers=262144 means 2 GB).  This converts them to
    conventional notation.
    """
    page_size = 8  # KB per page (PostgreSQL's default BLCKSZ)
    try:
        val = int(raw)
    except (ValueError, TypeError):
        return raw  # already human-readable (e.g. "on", "off")

    if name in ("work_mem",):
        # work_mem is in KB directly
        mb = val / 1024
        return f"{mb:.0f}MB" if mb >= 1 else f"{val}KB"
    if name in ("maintenance_work_mem",):
        mb = val / 1024
        unit = "MB" if mb >= 1 else "KB"
        return f"{mb:.0f}{unit}"
    if name in ("shared_buffers", "effective_cache_size"):
        # pages * 8KB = bytes; convert to GB/MB
        bytes_val = val * page_size * 1024
        gb = bytes_val / (1024 ** 3)
        if gb >= 1:
            return f"{gb:.0f}GB"
        mb = bytes_val / (1024 ** 2)
        return f"{mb:.0f}MB"
    if name in ("max_parallel_workers", "max_parallel_workers_per_gather"):
        return str(val)
    return raw


def _extract_field(text: str, key: str) -> str:
    """Pull a block labelled ``KEY:`` or **KEY:** out of free text."""
    import re
    # "key:" heading through next blank-line section
    m = re.search(rf"(?im)^{re.escape(key)}\s*[:：]\s*\n+(.+?)(?:\n\s*\n|\Z)", text)
    if m:
        return m.group(1).strip()
    m = re.search(rf"(?im)^{re.escape(key)}\s*[:：]\s*(.+)$", text)
    if m:
        return m.group(1).strip()
    return ""


# --------------------------------------------------------------------------- #
# MCP Tools
# --------------------------------------------------------------------------- #


@mcp.tool(
    name="hermes_reason",
    title="Hermes Reasoning",
    description=(
        "Send a task plus optional context to the local Ollama model "
        "(host GPU) and return structured JSON: summary, reasoning, "
        "recommendations, risks, follow_up_questions. "
        "Read-only — no shell, no SQL, no CRM writes, no file writes."
    ),
)
async def hermes_reason(
    ctx: Context,
    task: str,
    context: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """
    :param task:       The question or task to reason about.
    :param context:    Optional pre-fetched context (e.g. a query result
                       or a file excerpt) to ground the model.  The model
                       never fetches context itself.
    :param model:      Optional override for the Ollama model.  Defaults to
                       the ``HERMES_OLLAMA_MODEL`` env var or ``llama3.1``.
    :returns:          Structured JSON with keys: summary, reasoning,
                       recommendations, risks, follow_up_questions.
    """
    global OLLAMA_MODEL
    if model:
        OLLAMA_MODEL = model

    if not task or not task.strip():
        return {
            "summary": "No task provided.",
            "reasoning": "",
            "recommendations": [],
            "risks": ["The `task` parameter was empty."],
            "follow_up_questions": ["Provide a non-empty `task` string."],
            "isError": True,
        }

    try:
        raw = await call_ollama(task, context, ctx)
    except RuntimeError as exc:
        msg = str(exc)
        # If the model isn't found, give a clear hint.
        if "404" in msg or "not found" in msg.lower():
            msg += f"  Fix:  ollama pull {model or OLLAMA_MODEL}"
        return {
            "summary": "Ollama call failed.",
            "reasoning": "",
            "recommendations": [],
            "risks": [msg],
            "follow_up_questions": ["Is `ollama serve` running? Is the model pulled?"],
            "isError": True,
        }

    content = raw.get("message", {}).get("content", "")
    if not content:
        return {
            "summary": "Ollama returned an empty message.",
            "reasoning": "",
            "recommendations": [],
            "risks": ["Raw response had no message.content."],
            "follow_up_questions": ["Retry with a shorter task or check Ollama logs."],
            "isError": True,
        }

    parsed = parse_structured(content)
    parsed["model_used"] = raw.get("model", model or OLLAMA_MODEL)
    parsed["duration_ms"] = raw.get("total_duration", 0) / 1_000_000
    return parsed


@mcp.tool(
    name="hermes_job_status",
    title="Hermes Job Status",
    description=(
        "Read-only inspection of background jobs, Docker services, and "
        "dbt run artifacts.  Returns a structured status report.  No side "
        "effects — does not start, stop, or modify anything."
    ),
)
async def hermes_job_status(
    ctx: Context,
    which: str | None = None,
) -> dict[str, Any]:
    """
    :param which:  Optional filter — 'docker', 'dbt', or 'all' (default).
    :returns:      Structured JSON with current status of each subsystem.
    """
    target = (which or "all").lower()
    result: dict[str, Any] = {"services": {}, "dbt": {}, "overall": "unknown"}

    # --- Docker services ---
    if target in ("docker", "all"):
        compose_file = REPO_ROOT / DEFAULT_DOCKER_COMPOSE
        services: dict[str, Any] = {}
        if compose_file.exists():
            r = await _run_async([
                "docker", "compose", "-f", str(compose_file), "ps",
                "--format", "json",
            ])
            if r.returncode == 0 and r.stdout.strip():
                for line in r.stdout.strip().splitlines():
                    try:
                        svc = json.loads(line)
                        services[svc.get("Service", "?")] = {
                            "status": svc.get("Status", "unknown"),
                            "state": svc.get("State", "unknown"),
                            "health": svc.get("Health", ""),
                        }
                    except json.JSONDecodeError:
                        continue
            else:
                services["note"] = r.stderr.strip()[:200] or "docker compose ps failed / no containers"
        else:
            services["error"] = f"compose file not found: {compose_file}"
        result["services"] = services

    # --- dbt run artifacts ---
    if target in ("dbt", "all"):
        dbt_dir = REPO_ROOT / DEFAULT_DBT_TARGET
        dbt_info: dict[str, Any] = {}
        if dbt_dir.exists():
            # Check for a recent run_results.json
            rr = dbt_dir / "target" / "run_results.json"
            if rr.exists():
                try:
                    data = json.loads(rr.read_text())
                    dbt_info["latest_run_results"] = {
                        "success": data.get("success", "unknown"),
                        "elapsed_seconds": round(data.get("elapsed_time", 0), 2),
                        "num_models": len(data.get("results", [])),
                        "generated_at": data.get("metadata", {}).get("generated_at", ""),
                    }
                except (json.JSONDecodeError, TypeError):
                    dbt_info["latest_run_results"] = {"error": "could not parse run_results.json"}
            else:
                dbt_info["latest_run_results"] = "run_results.json not found — dbt has not been run or target/ is absent"
        else:
            dbt_info["error"] = f"dbt directory not found: {dbt_dir}"
        result["dbt"] = dbt_info

    # --- overall ---
    svc_down = [k for k, v in result.get("services", {}).items()
                if isinstance(v, dict) and v.get("state", "").lower() not in ("running", "up") and k != "note" and k != "error"]
    if not svc_down and result.get("services"):
        result["overall"] = "healthy"
    elif svc_down:
        result["overall"] = "degraded"
    result["risks"] = [f"Services not 'Up': {svc_down}"] if svc_down else []

    return result


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _run_async(cmd: list[str]) -> Any:
    """Run a subprocess asynchronously (non-blocking for the MCP loop)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30),
    )


@mcp.tool(
    name="hermes_resource_status",
    title="Resource Status Probe (proposal-only)",
    description=(
        "Read-only probe that reports the configured state of the local "
        "data stack (Postgres tuning values, Ollama model availability, "
        "dbt threads).  Returns a JSON snapshot.  This is a *read* tool — "
        "it suggests actions but never executes them.  Any suggestion that "
        "would touch HubSpot is dry-run / proposal-only."
    ),
)
async def hermes_resource_status(ctx: Context) -> dict[str, Any]:
    """Snapshot current local-stack resources.  Read-only."""
    snapshot: dict[str, Any] = {}

    # --- Postgres tuning (if the container is up) ---
    compose_file = REPO_ROOT / DEFAULT_DOCKER_COMPOSE
    pg_settings = {}
    if compose_file.exists():
        r = await _run_async([
            "docker", "compose", "-f", str(compose_file), "exec", "-T", "postgres",
            "psql", "-U", "revops", "-d", "revops", "-tA",
            "-c", "SELECT name||'='||setting FROM pg_settings "
            "WHERE name IN ('shared_buffers','work_mem','maintenance_work_mem',"
            "'effective_cache_size','max_parallel_workers','max_parallel_workers_per_gather');",
        ])
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    pg_settings[k] = _humanize_pg_setting(k, v)
        if not pg_settings:
            pg_settings["note"] = "Postgres container not reachable — is `docker compose up` running?"
    snapshot["postgres_tuning"] = pg_settings

    # --- Ollama model availability ---
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            tags = json.loads(resp.read().decode())
        models = [m["name"] for m in tags.get("models", [])]
    except Exception as exc:
        models = []
        snapshot["ollama_error"] = str(exc)[:200]
    snapshot["ollama_models"] = models
    snapshot["ollama_default_model"] = OLLAMA_MODEL
    # Handle Ollama's ":latest" tag suffix — "llama3.1" matches "llama3.1:latest"
    available_names = set()
    for m in models:
        available_names.add(m)
        if m.endswith(":latest"):
            available_names.add(m[:-len(":latest")])
    snapshot["ollama_model_available"] = OLLAMA_MODEL in available_names

    # --- dbt threads ---
    profiles = REPO_ROOT / "transform" / "profiles.yml"
    dbt_threads = None
    dbt_profile = None
    if profiles.exists():
        try:
            prof = _parse_yaml(profiles.read_text())
            out = prof.get("revops", {}).get("outputs", {}).get("dev", {})
            dbt_threads = out.get("threads")
            dbt_profile = "revops"
        except Exception as exc:
            # Fallback: regex for threads:<N> in profiles.yml
            import re
            m = re.search(r"threads\s*:\s*(\d+)", profiles.read_text().split("revops")[1] if "revops" in profiles.read_text() else profiles.read_text())
            if m:
                dbt_threads = int(m.group(1))
                dbt_profile = "revops (parsed via regex)"
    snapshot["dbt_threads"] = dbt_threads
    snapshot["dbt_profile"] = dbt_profile

    # --- cpu / mem sizing (informational) ---
    try:
        r = await _run_async(["/usr/sbin/sysctl", "-n", "hw.ncpu", "hw.memsize"])
        if r.returncode != 0:
            r = await _run_async(["sysctl", "-n", "hw.ncpu", "hw.memsize"])
        if r.returncode == 0:
            parts = r.stdout.strip().splitlines()
            if len(parts) >= 2:
                snapshot["host_cpus"] = int(parts[0])
                snapshot["host_ram_gb"] = round(int(parts[1]) / 1e9, 1)
    except Exception:
        pass

    return snapshot


# --------------------------------------------------------------------------- #
# Entry point (stdio transport — never opens a network port)
# --------------------------------------------------------------------------- #

def main() -> None:
    """Run the Hermes MCP server over stdio."""
    # Validate that the Ollama host is reachable (clear error on startup if not).
    try:
        req = urllib.request.Request("http://localhost:11434/api/version")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Ollama returned HTTP {resp.status}")
    except Exception:
        # We don't hard-fail startup — tools will return clear errors at call-time.
        import sys
        sys.stderr.write(
            "WARNING: Ollama not reachable at http://localhost:11434 — "
            "ensure `ollama serve` is running with model "
            f"{OLLAMA_MODEL}. Tools will return errors until it is up.\n"
        )
        sys.stderr.flush()

    # Verify the configured model is available (pull hint on mismatch).
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=10) as resp:
            tags = json.loads(resp.read().decode())
        models = [m["name"] for m in tags.get("models", [])]
        # Handle ":latest" suffix — "llama3.1" matches "llama3.1:latest"
        available = set(models)
        for m in models:
            if m.endswith(":latest"):
                available.add(m[:-len(":latest")])
        if OLLAMA_MODEL not in available:
            import sys
            sys.stderr.write(
                f"WARNING: model '{OLLAMA_MODEL}' not found in Ollama registry. "
                f"Run:  ollama pull {OLLAMA_MODEL}\n"
            )
            sys.stderr.flush()
    except Exception:
        pass  # startup already warned about host unreachable

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
