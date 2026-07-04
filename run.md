# Running the harness

## Prerequisites

- Python 3.12+
- [Ollama](https://ollama.com/download) installed and running
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for Python package management

---

## 1. Install Ollama and pull a model

Ollama runs models locally. The harness defaults to `qwen3:8b`, which supports
tool calling. Install Ollama, then pull the model:

```bash
# macOS
brew install ollama

# Pull the default model (one-time, ~5 GB)
ollama pull qwen3:8b

# Start the Ollama server (keep this running in a terminal)
ollama serve
```

Verify it is working:

```bash
ollama list          # should show qwen3:8b
curl http://localhost:11434/api/tags   # should return JSON
```

To use a different model, set the env var before running:

```bash
HARNESS_MODEL=llama3.1 python agent.py
```

Other tool-calling-capable models available via Ollama: `llama3.1`, `mistral-nemo`,
`qwen2.5`, `firefunction-v2`.

---

## 2. Set up the Python environment

```bash
# Create the virtual environment
uv venv .venv

# Activate it (run this in every new terminal session)
source .venv/bin/activate

# Install all dependencies
uv pip install arize-phoenix \
               opentelemetry-sdk \
               opentelemetry-exporter-otlp-proto-http \
               openinference-semantic-conventions \
               ollama
```

Dependencies explained:

| Package | Purpose |
|---|---|
| `ollama` | Python client for the local Ollama HTTP API |
| `arize-phoenix` | Local tracing UI + OTLP collector |
| `opentelemetry-sdk` | Core OTEL span/trace machinery |
| `opentelemetry-exporter-otlp-proto-http` | Ships spans to Phoenix over HTTP |
| `openinference-semantic-conventions` | LLM-specific span attribute names (model, tokens, tool name) |

---

## 3. Start Phoenix (tracing UI)

Phoenix is the local observability dashboard. Run it in a separate terminal:

```bash
source .venv/bin/activate
phoenix serve
```

Phoenix starts on **http://localhost:6006** by default. Open that URL in your browser.
Traces appear after each REPL interaction.

To use a different port:

```bash
PHOENIX_PORT=7007 phoenix serve
```

If you change the port, update `PHOENIX_ENDPOINT` in `util/tracing.py` to match.

---

## 4. Run the agent

In a third terminal (with Ollama already running in one and Phoenix in another):

```bash
source .venv/bin/activate
python agent.py
```

You will see the REPL prompt:

```
PM spec assistant ready.  /skills to browse, /use <name> to activate.

you>
```

Type a request or a slash command (see below). The session stays alive across
turns — message history accumulates so the model remembers context.

### Example session

```
you> /skills
Available skills:
  interpret-north-star
  write-acceptance-criteria
  write-tech-spec

you> /use write-tech-spec
  Skill 'write-tech-spec' activated. Active: ['write-tech-spec']

you> I want to write a tech spec for a user search feature
  [tool] list_dir(path='specs/')
  [done] list_dir -> specs/ is empty

<model asks clarifying questions, then begins drafting>

you> save it to specs/search-tech-spec.md
  [tool] write_file(path='specs/search-tech-spec.md', content='...')

[permission] write_file wants to run with:
             path: specs/search-tech-spec.md
             content: # Search Feature — Technical Spec...
Allow? [y/N] y
  [done] write_file -> wrote 1842 bytes to specs/search-tech-spec.md
```

---

## 5. Slash commands

| Command | What it does |
|---|---|
| `/skills` | List all available skills in `skills/` |
| `/use <name>` | Activate a skill for the rest of this session |
| `/active` | Show which skills are currently active |
| `/clear-skills` | Reset to base PM persona, no active skills |
| `quit` / `exit` | End the session |

---

## 6. Configuration

All defaults are set in `config/settings.py` and can be overridden with environment
variables — no file edits needed:

| Env var | Default | What it controls |
|---|---|---|
| `HARNESS_MODEL` | `qwen3:8b` | Ollama model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `HARNESS_MAX_TURNS` | `10` | Max tool-call loop iterations before giving up |
| `AGENTS_MD_PATH` | `AGENTS.md` | Path to the agent persona file |

Example — run against a different model:

```bash
HARNESS_MODEL=llama3.1 HARNESS_MAX_TURNS=5 python agent.py
```

---

## 7. Tools available to the agent

| Tool | Backend | What it does | Permission |
|---|---|---|---|
| `scrape_url` | Python script | Fetch a URL, return stripped text | Auto |
| `read_file` | MCP stdio | Read a file by path | Auto |
| `list_dir` | MCP stdio | List directory contents | Auto |
| `write_file` | MCP stdio | Write a file to disk | Prompts [y/N] |

The stdio tools run in a subprocess (`tool/stdio/server.py`) that is spawned once
at startup and reused for the session. You do not need to start it manually.

---

## 8. What to look at in Phoenix

After a run, open **http://localhost:6006 → Traces**. Click any trace row to expand it:

```
chain                    ← root span for one session.send() call
  └── llm                 ← Ollama API call (system prompt + history + schemas)
  └── tool: list_dir       ← tool execution (name, input, output)
  └── llm                  ← next Ollama call with tool result injected
  └── tool: write_file
  └── llm                  ← final response
```

Useful things to inspect per span:

- `input.value` on an `llm` span — the exact message list sent to the model
- `output.value` on a `tool` span — what the tool actually returned
- `llm.token_count.prompt` / `llm.token_count.completion` — token usage
- Span duration — where latency is coming from (model vs tool)

---

## 9. Terminal layout (recommended)

```
Terminal 1: ollama serve
Terminal 2: source .venv/bin/activate && phoenix serve
Terminal 3: source .venv/bin/activate && python agent.py
```
