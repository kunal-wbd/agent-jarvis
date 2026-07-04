# TODO

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
