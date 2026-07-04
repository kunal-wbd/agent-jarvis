# Harness Architecture

A hand-rolled agent loop built to learn the mechanics of multi-agent, multi-skill, and
MCP-connected systems. No agent frameworks — every layer is explicit Python so the loop
is observable and modifiable.

---

## Operating flow

```
User types a message in the REPL
        │
        ▼
agent.py — REPL loop
  ├── slash command? (/project, /skills, /use, /active, /clear-skills)
  │       └── handle locally, never sent to model
  └── plain text?
          └── session.send(user_message)
                  │
                  ▼
          session/session.py — agent loop (bounded by MAX_TURNS)
            │
            ├── 1. append user message to messages[]
            │
            ├── 2. provider/ollama.py — complete(messages, tools)
            │         sends: system prompt + full message history + tool schemas
            │         returns: ModelResponse(text, tool_calls[])
            │         emits: llm OTEL span (input, output, token counts)
            │
            ├── 3. no tool_calls?
            │         yield Event("text") → print to terminal → DONE
            │
            └── 4. tool_calls present?
                      ├── yield Event("tool_call")
                      ├── permission/permission.py — check(name, input)
                      │         read-only tools: auto-approved
                      │         side-effect tools: prompts user [y/N]
                      ├── tool/registry.py — run_tool(name, input)
                      │         scripts backend  → call module.run()
                      │         stdio backend    → StdioClient.call() via JSON-RPC
                      │         sse backend      → SSEClient.call() (placeholder)
                      │         emits: tool OTEL span
                      ├── append tool result to messages[]
                      ├── yield Event("tool_result")
                      └── go to step 2 (repeat with updated messages)
```

---

## System prompt construction

The system prompt sent to the model on every call is assembled at session start
and can be updated mid-session when the user activates a skill.

```
messages[0] = {role: system, content:
    [agents.md — base PM persona]
    +
    [## Active project]             ← appended when /project <name> is set
    [project path + file-op scope]
    +
    [## Active skills]              ← appended when /use <skill> is called
    [skills/<name>.md]              ← full skill file content, one per --- separator
    [skills/<name>.md]              ← multiple skills can be active simultaneously
}
```

`session.set_system_prompt(text)` patches `messages[0]` in place so any state change
(project switch, skill activation, skill clear) takes effect for the next model call
without losing conversation history. All prompt rebuilds go through `_rebuild_prompt()`
to ensure project context and active skills are always assembled together.

---

## Tool discovery

The registry (`tool/registry.py`) runs discovery for all three backends at import time
and merges results into a single flat namespace.

```
tool/registry.py — discover() at import
  │
  ├── scripts: pkgutil.iter_modules(tool/scripts/)
  │     any .py with SCHEMA + run() is auto-registered
  │     → scrape_url
  │
  ├── stdio:  StdioClient.instance() → tools/list JSON-RPC
  │     spawns tool/stdio/server.py as subprocess once at startup
  │     → read_file, write_file, list_dir
  │
  └── sse:    SSEClient.list_tools()  [placeholder → empty]
```

`run_tool(name, input)` routes to the correct backend transparently. The session
layer has no knowledge of which backend handles a given tool.

`discovered_tools()` returns `{tool_name: backend}` for debugging.

---

## Project directory layout

```
harness/
│
├── agent.py                    entry point — multi-turn REPL + slash command handler
├── agents.md                   base system prompt: Principal Technical PM persona
│
├── skills/                     skill files — injected into system prompt on demand
│   ├── interpret-north-star.md   break a north star doc into Problem/Goals/etc.
│   ├── write-tech-spec.md        write a tech spec section by section
│   └── write-acceptance-criteria.md  produce Given/When/Then criteria
│
├── config/
│   └── settings.py             env-var-driven config (model, host, max turns, paths)
│
├── session/
│   ├── event.py                Event dataclass: text | tool_call | tool_result | max_turns
│   ├── session.py              Session: message history + agent loop + set_system_prompt()
│   └── system.py               load_system_prompt(active_skills) — assembles messages[0]
│
├── provider/
│   └── ollama.py               sole Ollama caller; normalises response to ModelResponse
│
├── tool/
│   ├── registry.py             unified discovery + routing across all backends
│   │
│   ├── scripts/                direct Python tools — imported inline, no subprocess
│   │   ├── scrape.py             scrape_url: fetch URL → stripped text
│   │   └── roadmap.md
│   │
│   ├── stdio/                  MCP stdio tools — JSON-RPC over subprocess pipes
│   │   ├── server.py             MCP server: read_file, write_file, list_dir
│   │   ├── client.py             MCP client: singleton subprocess + JSON-RPC wrapper
│   │   └── roadmap.md
│   │
│   └── sse/                    MCP SSE tools — remote HTTP servers (placeholder)
│       ├── client.py             SSEClient stub
│       └── roadmap.md
│
├── permission/
│   └── permission.py           side-effect gate: auto-approve reads, prompt for writes
│
├── util/
│   └── tracing.py              OTEL setup — BatchSpanProcessor → Phoenix localhost:6006
│
├── projects/                   generated project directories (git-ignored)
│   └── <project-name>/           created by /project <name> command
│       ├── specs/
│       ├── acceptance-criteria/
│       └── decisions/
├── tests/
│   ├── test_permission.py      permission gate: auto-approve vs prompt
│   ├── test_scrape_tool.py     scrape_url: HTML stripping, truncation, errors
│   ├── test_stdio_server.py    MCP server handlers: read/write/list/unknown
│   └── test_system_prompt.py  prompt assembly: base, project, skills, combinations
├── README.md                   project overview and quick-start
├── run.md                      full setup, operational guide, and example session
└── architecture.md             this file
```

---

## Per-project directory convention

Each project gets its own directory under `projects/` (created by `/project <name>`).
The system prompt tells the model to scope all file operations to this path and to
call `list_dir` before creating anything.

```
projects/
└── <project-name>/
    ├── specs/
    │   ├── <feature>-prd.md
    │   └── <feature>-tech-spec.md
    ├── acceptance-criteria/
    │   └── <feature>-ac.md
    └── decisions/
        └── <feature>-adr.md
```

`HARNESS_PROJECTS_DIR` env var overrides the default `projects/` root.

---

## Skills system

Skills are markdown files in `skills/`. They contain behavioral instructions appended
to the system prompt when activated. The model sees them as part of its persona.

| Skill | Activated with | Purpose |
|---|---|---|
| `interpret-north-star` | `/use interpret-north-star` | Read a north star doc → Problem, Goals, Non-goals, User stories, Metrics, Open questions |
| `write-tech-spec` | `/use write-tech-spec` | Draft a technical spec section by section with confirmation at each step |
| `write-acceptance-criteria` | `/use write-acceptance-criteria` | Convert a spec into Given/When/Then acceptance criteria |

Skills are lazy-loaded: absent from the system prompt until explicitly activated.
Multiple skills can be active simultaneously. `/clear-skills` resets to base persona.

**Adding a skill:** create `skills/<name>.md`. It appears in `/skills` immediately —
no code changes required.

---

## Tools

| Tool | Backend | Side effect | Permission |
|---|---|---|---|
| `scrape_url` | scripts | No | Auto |
| `read_file` | stdio (MCP) | No | Auto |
| `list_dir` | stdio (MCP) | No | Auto |
| `write_file` | stdio (MCP) | Yes — writes to disk | Prompts [y/N] |

### Adding a scripts tool

1. Create `tool/scripts/<name>.py` with `SCHEMA` (OpenAI function format) and `run(**kwargs) -> str`.
2. Auto-discovered — no registry edit needed.

### Adding a stdio tool

1. Add a handler function in `tool/stdio/server.py`.
2. Register it in `_TOOLS` with its `inputSchema`.
3. Restart the harness — `StdioClient` calls `tools/list` at startup and picks it up.

### Adding a side-effect tool

Add the tool name to `SIDE_EFFECT_TOOLS` in `permission/permission.py`.

---

## Observability

Every run emits OpenTelemetry spans to Arize Phoenix at `http://localhost:6006`.

```
chain                      ← root span for one session.send() call
  └── llm                   ← Ollama API call (full message list, model output, tokens)
  └── tool: list_dir         ← tool execution (name, input args, string result)
  └── llm                   ← next call with tool result injected
  └── tool: write_file
  └── llm                   ← final response (no tool_calls)
```

OpenInference attributes on each span:
- `llm` spans: `llm.model_name`, `input.value`, `output.value`, `llm.token_count.*`
- `tool` spans: `tool.name`, `input.value`, `output.value`
- `chain` spans: `input.value` (user message), `output.value` (final response)

---

## Configuration

| Env var | Default | Controls |
|---|---|---|
| `HARNESS_MODEL` | `qwen3:8b` | Ollama model (must support tool calling) |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `HARNESS_MAX_TURNS` | `10` | Max tool-call iterations before giving up |
| `AGENTS_MD_PATH` | `agents.md` | Path to the base persona file |
| `HARNESS_PROJECTS_DIR` | `projects` | Root directory for per-project workspaces |

---

## Roadmap

```
Phase 2 — stdio expansion (tool/stdio/roadmap.md)
  Add git ops, shell exec, grep — all as stdio MCP tools in server.py

Phase 3 — SSE tools (tool/sse/roadmap.md)
  Implement SSEClient; connect to Notion, Linear, GitHub, Slack

Phase 4 — Multi-agent
  agent/
  ├── orchestrator.py     routes tasks to specialist agents by type
  └── specialist.py       a Session with a narrower persona + skill set

Phase 5 — Skills expansion (skills/)
  Additional PM skills: competitive analysis, user interview synthesis,
  OKR decomposition, release notes
```
