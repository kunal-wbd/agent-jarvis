# harness

A framework-free agent harness for learning how multi-agent, multi-skill, and
MCP-connected systems work under the hood. Runs local models via
[Ollama](https://ollama.com) — no cloud APIs or proprietary SDKs.

Built around a hand-rolled agent loop: every layer (model call, tool dispatch,
permission gate, observability) is explicit Python you can read and change.

Current use case: an interactive product spec writing assistant driven by a
Principal Technical PM persona.

---

## Quick start

```bash
uv venv .venv && source .venv/bin/activate
uv pip install arize-phoenix opentelemetry-sdk \
               opentelemetry-exporter-otlp-proto-http \
               openinference-semantic-conventions ollama

ollama pull qwen3:8b   # one-time, ~5 GB
ollama serve           # keep running in a separate terminal

phoenix serve          # tracing UI at http://localhost:6006

python agent.py        # start the REPL
```

See `run.md` for full setup instructions.

---

## Directory structure

```
agent.py                 Multi-turn REPL — slash command handler + event printer
agents.md                Base system prompt: Principal Technical PM persona
skills/                  Skill files injected into the system prompt on demand
  interpret-north-star.md
  write-tech-spec.md
  write-acceptance-criteria.md

config/
  settings.py            Env-var config: model, host, max turns, paths

session/
  event.py               Event dataclass (text | tool_call | tool_result | max_turns)
  session.py             Session class: message history + agent loop
  system.py              Assembles system prompt from agents.md + active skills

provider/
  ollama.py              Only file that calls Ollama. Returns ModelResponse(text, tool_calls).

tool/
  registry.py            Unified discovery: aggregates scripts, stdio, and SSE tools
  scripts/               Direct Python tools (stateless, no subprocess)
    scrape.py              scrape_url — fetch a URL and return stripped text
    roadmap.md
  stdio/                 MCP stdio tools (disk ops via JSON-RPC subprocess)
    server.py              MCP server: read_file, write_file, list_dir
    client.py              MCP client: spawns server, manages subprocess lifecycle
    roadmap.md
  sse/                   MCP SSE tools (remote HTTP servers — placeholder)
    client.py
    roadmap.md

permission/
  permission.py          Gates side-effect tools; prompts [y/N] before write_file

util/
  tracing.py             OTEL setup → Arize Phoenix at localhost:6006

specs/                   Generated spec output (per-project subdirectories)
tests/                   Test stubs
architecture.md          Full architecture reference
run.md                   Setup and operational instructions
```

---

## Agent loop

```
REPL input
  → slash command?  handle locally (/skills, /use, /active, /clear-skills)
  → plain text?     session.send(text)
      → complete(messages, tool_schemas)   [Ollama]
      → tool_calls?
          → permission.check()             [prompt user if side-effect]
          → run_tool()                     [scripts / stdio / sse]
          → append result → loop
      → no tool_calls → yield text → done
```

---

## Skills (REPL commands)

| Command | Effect |
|---|---|
| `/skills` | List all `.md` files in `skills/` |
| `/use <name>` | Inject that skill into the system prompt for this session |
| `/active` | Show which skills are currently active |
| `/clear-skills` | Reset to base persona only |

---

## Tools

| Tool | Backend | Side effect |
|---|---|---|
| `scrape_url` | scripts | No |
| `read_file` | stdio (MCP) | No |
| `list_dir` | stdio (MCP) | No |
| `write_file` | stdio (MCP) | Yes — prompts [y/N] |

### Adding a tool

**Scripts** — create `tool/scripts/<name>.py` with `SCHEMA` and `run()`. Auto-discovered.

**Stdio** — add a handler function and an entry in `_TOOLS` inside `tool/stdio/server.py`.
The client picks it up via `tools/list` at next startup.

**SSE** — not yet implemented. See `tool/sse/roadmap.md`.

---

## Per-project layout

Each project the agent works on gets its own directory:

```
{project}/
├── specs/
│   ├── <feature>-prd.md
│   └── <feature>-tech-spec.md
├── acceptance-criteria/
│   └── <feature>-ac.md
└── decisions/
    └── <feature>-adr.md
```

---

## Swapping the model

All Ollama-specific code is in `provider/ollama.py`. To point at a different runtime
(llama.cpp, vLLM), write a module with the same `complete(messages, tools) -> ModelResponse`
signature and import it in `session/session.py`.

Tool-calling-capable models: `qwen3:8b` (default), `llama3.1`, `qwen2.5`, `mistral-nemo`.
