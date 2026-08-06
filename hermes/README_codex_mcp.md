# Hermes MCP Bridge for Codex

A local [Model-Context Protocol](https://modelcontextprotocol.io) (MCP) **stdio**
server named `hermes` that bridges Codex to the project's local Ollama LLM and
read-only warehouse/Git state.

> **Read-only by design.** See the [safety contract](#safety-contract) below.

---

## Quick start

### 1. Install dependencies (one-time)

```bash
# From the repo root, with the project venv active:
.venv/bin/python -m pip install -r requirements.txt
# Or with uv:
uv pip install -r requirements.txt
```

The `mcp>=1.28,<1.29` line pulls the FastMCP server API used by the bridge.

### 2. Ensure Ollama is running with a model

```bash
brew services start ollama          # or: ollama serve
ollama pull llama3.1                # project default model
```

The server talks to Ollama over the **host** loopback
(`http://localhost:11434/api/chat`).  No Docker port mapping is needed.

### 3. Configure Codex

Claude Code's MCP integration picks up servers from a config file.  Add the
following entry:

```jsonc
// .codex/mcp.json  (or wherever your MCP config lives)
{
  "mcpServers": {
    "hermes": {
      "command": "/Users/AidanMDuffy/Desktop/Hermes/revops-data-platform/.venv/bin/python",
      "args": [
        "/Users/AidanMDuffy/Desktop/Hermes/revops-data-platform/hermes/codex_mcp.py"
      ],
      "env": {
        "HERMES_OLLAMA_MODEL": "llama3.1",
        "HERMES_OLLAMA_HOST": "http://localhost:11434/api/chat"
      }
    }
  }
}
```

> `HERMES_OLLAMA_MODEL` defaults to `llama3.1` if unset.  Override per-session
> by changing `args` or the env block above.

### 4. Verify the bridge works

```bash
# Echo test: pipe an MCP `initialize` request over stdio.
exec 3>&1
{ printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"codex-test","version":"0"}}}' ; sleep 1 ; } | \
  .venv/bin/python hermes/codex_mcp.py 2>/dev/null | head -1 | python3 -m json.tool
exec 3>&-

# Expected: a JSON object with "result" containing serverCapabilities
# including "tools": [{"name":"hermes_reason"}, {"name":"hermes_job_status"}, ...].
```

Or, from any MCP-aware client (e.g. Claude Code once configured):

> **codex-mcp.py:** what tools are available?

The server should list `hermes_reason`, `hermes_job_status`, and
`hermes_resource_status`.

---

## Available tools

### `hermes_reason`

Send a task (plus optional pre-fetched context) to the local Ollama model and
receive structured analysis.

| Parameter   | Type     | Required | Description |
|-------------|----------|----------|-------------|
| `task`      | string   | yes      | The question or task to reason about. |
| `context`   | string   | no       | Optional grounding facts (e.g. a raw query result). The model never fetches context itself. |
| `model`     | string   | no       | Override the Ollama model. Defaults to `HERMES_OLLAMA_MODEL` or `llama3.1`. |

**Returns** a JSON object:
```json
{
  "summary": "One-sentence takeaway",
  "reasoning": "Concise chain-of-thought",
  "recommendations": ["actionable items"],
  "risks": ["assumptions or caveats"],
  "follow_up_questions": ["next-step questions"],
  "model_used": "llama3.1",
  "duration_ms": 412
}
```

### `hermes_job_status`

Read-only status of Docker services and dbt run artifacts.

| Parameter | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `which`   | string | no       | Filter: `docker`, `dbt`, or `all` (default). |

### `hermes_resource_status`

Read-only snapshot of the local stack: Postgres tuning values, Ollama model
availability, dbt threads, and host CPU/RAM sizing.

---

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HERMES_OLLAMA_MODEL` | `llama3.1` | Ollama model name for chat API calls. |
| `HERMES_OLLAMA_HOST` | `http://localhost:11434/api/chat` | Ollama chat endpoint URL. |
| `HERMES_MAX_TOKENS` | `1024` | Max output tokens per request. |
| `HERMES_OLLAMA_TIMEOUT` | `60` | HTTP request timeout (seconds). |

---

## Safety contract

This server enforces a hard read-only boundary:

- ✅ Local LLM reasoning (host GPU, Ollama chat API)
- ✅ Read-only Docker service inspection (`docker compose ps`)
- ✅ Read-only dbt artifact inspection (`run_results.json`)
- ✅ Read-only Postgres tuning snapshot (`SHOW` via `psql`)
- ✅ Read-only Ollama model list (`/api/tags`)
- ✅ Host CPU/RAM sizing (`sysctl`)

**Not exposed (by design):**

- ❌ Shell execution
- ❌ Arbitrary SQL execution
- ❌ HubSpot writes (and any future HubSpot tool is proposal-only / dry-run)
- ❌ Environment-variable dumping
- ❌ File writes
- ❌ Network server / port binding (stdio transport only)

If any of these become necessary in a future tool, the default must be
dry-run / proposal-only, and the change must be reviewed in a PR.
