# TODO

## Tech Debt

- [ ] **Hard-coded tool references in `load_system_prompt`** — `session/system.py:load_system_prompt`
  builds the system prompt from `AGENTS_MD_PATH` but any description of available tools
  is a static string baked into `agents.md` by hand. When a new tool module is added to
  `tool/registry.py`, the system prompt does not automatically reflect it, causing drift
  between what the model is told it can do and what `SCHEMAS` actually exposes.
  Fix: derive the tool list at runtime from `tool/registry.py:SCHEMAS` (name +
  description fields) and inject it as a generated section in the system prompt, so
  `agents.md` only carries agent-level instructions, not a tool inventory.
  **Priority:** Medium — currently low risk (small tool set) but will cause silent model
  confusion as tools expand.

## Short term

- [ ] **Short-term memory optimization** — the full message history is sent to the model
  on every call. As conversations grow, this inflates token count and latency. Options:
  - Sliding window: keep only the last N turns in `messages[]`
  - Summarization: periodically compress older turns into a single summary message
  - Relevance trimming: drop tool results beyond a recency threshold

## Backlog

- [ ] Pick and commit to a repo codename
- [ ] GitHub repo init and first commit
- [ ] Add pytest to `pyproject.toml` dev dependencies and document `uv pip install -e ".[dev]"`
- [ ] stdio tool expansion — git ops, grep, shell (see `tool/stdio/roadmap.md`)
- [ ] SSE client implementation (see `tool/sse/roadmap.md`)
- [ ] Additional PM skills — competitive analysis, OKR decomposition, release notes
- [ ] Multi-agent: orchestrator + specialist session routing
