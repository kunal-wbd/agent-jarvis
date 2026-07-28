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

- [ ] **Empty session rows clutter `/sessions`** — `memory/store.py:register_session` inserts
  a row the moment a `Session` is constructed, which is what makes switch-away-and-back
  resume work (PR #2). The side effect is that every `/project` switch and every harness
  startup leaves a row with `turn_count: 0` and no messages. `/sessions` currently lists
  these empty shells alongside real conversations — 8 of 10 rows at time of writing.
  Fix: filter `list_sessions()` to `turn_count > 0` by default, with a `--all` flag to
  show everything; optionally add a `prune_empty_sessions()` maintenance function.
  **Priority:** Low — cosmetic, but degrades `/sessions` usefulness as rows accumulate.

- [ ] **`_llm_ingest` is a stub and is unregistered** — `tool/stdio/server.py:_llm_ingest`
  has a docstring describing a document-ingestion pipeline but a two-line body that reads
  `sys.argv` (meaningless in the stdio subprocess — the `path` argument is ignored) and
  returns `None`, which raises `TypeError` in `StdioClient.call`'s result join. Its
  `_TOOLS` entry is commented out so the model cannot call it and break a session.
  Fix: split it along the tool/skill boundary — a tool `convert_document(path) -> str`
  that turns a PDF/DOCX/PPTX into markdown text (via `markitdown`), and a skill that
  tells the model what to extract from that text and which wiki pages to write.
  A stdio tool cannot itself "read the source and extract knowledge" — it has no model
  access. Re-register once the handler returns a string.
  **Priority:** Medium — blocked capability, but no longer a crash risk.

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


## LLM Wiki — Learning Plan

A progressive build toward GBrain-level capability. Each phase teaches one concept
before the next builds on it. Implement in order — later phases assume earlier ones.

### Phase W1 — Foundation (implement first)
*Goal: get a working wiki that persists structured facts and retrieves them.*

- [ ] **`wiki/store.py`** — markdown file I/O + SQLite embedding index
  - Write/read pages under `PRD/<project>/wiki/`
  - YAML frontmatter (page path, updated_at, source_session_id)
  - SQLite table: `wiki_index(project, page_path, chunk_text, embedding BLOB, updated_at)`
  - `write_page`, `read_page`, `list_pages`, `upsert_embedding`, `search` (cosine in Python)
  - *Learn:* how to serialize float32 vectors with `struct.pack`; cosine similarity without a vector DB

- [ ] **`wiki/retriever.py`** — embed query → cosine search → format context block
  - Embed user message via `ollama.embed("nomic-embed-text", text)`
  - Return top-3 chunks as a `[WIKI CONTEXT]` block injected before the model call
  - *Learn:* embedding vs. generation models; why retrieval latency matters

- [ ] **`wiki/extractor.py`** — ask model to extract facts after each turn
  - Prompt: "identify new decisions, requirements, or open questions from this exchange"
  - Parse → append facts to the right page → re-embed
  - Run in a background `threading.Thread` so it doesn't block the REPL
  - *Learn:* LLM-as-extractor pattern; async side effects in a sync loop

- [ ] **Wire into `session/session.py`** — context before call, extraction after
- [ ] **`/wiki` slash commands** in `agent.py`: list pages, show page, reindex
- [ ] **`run.md` update** — add `ollama pull nomic-embed-text` step

---

### Phase W2 — Gap Analysis
*Goal: the agent knows what it doesn't know. Inspired by `gbrain think`.*

- [ ] **Gap analysis in the synthesis prompt** — after injecting wiki context, instruct
  the model to explicitly note if its answer relies on information the wiki lacks
  - No new code — just prompt engineering in `wiki/retriever.py`
  - *Learn:* how system prompt framing changes model confidence calibration

- [ ] **`create_safety` hint** — before writing a new fact, check if a semantically
  similar chunk already exists (cosine threshold ~0.92); skip or merge if so
  - Prevents duplicate facts accumulating across sessions
  - *Learn:* deduplication via embedding similarity; threshold tuning

- [ ] **Staleness tagging** — track `updated_at` per chunk; surface in context block
  when a retrieved chunk is > N days old
  - *Learn:* time-aware retrieval; why recency signals matter alongside relevance

---

### Phase W3 — Lightweight Knowledge Graph
*Goal: structured relationships between entities, not just flat text chunks.*
*Inspired by GBrain's self-wiring graph (+31.4 P@5 over vector-only RAG).*

- [ ] **`relations` table in SQLite** — `(source_page, relation_type, target_page)`
  - Relation types: `depends_on`, `decided_by`, `implements`, `blocks`, `related_to`
  - *Learn:* why graph edges find things vector search misses

- [ ] **Auto-link on page write** — regex scan for `[[page-name]]` wikilink syntax;
  insert edges into `relations`; zero LLM calls
  - *Learn:* GBrain's core insight: pattern matching beats LLM extraction for structural links

- [ ] **Graph-aware retrieval** — expand top-K results by one hop via `relations`
  - *Learn:* graph traversal as a retrieval signal; hub pages; recall vs. precision tradeoff

- [ ] **`/wiki graph <page>`** — show a page's inbound + outbound edges

---

### Phase W4 — Hybrid Search
*Goal: combine vector similarity with keyword matching for better recall.*
*Inspired by GBrain's vector + BM25 + RRF stack.*

- [ ] **BM25 keyword scoring** — `rank-bm25` (pure Python); merge with cosine via
  reciprocal rank fusion (RRF)
  - *Learn:* why BM25 finds exact-match queries embeddings miss (names, versions, acronyms);
    how RRF combines ranked lists without knowing each list's score scale

- [ ] **Named-entity boosting** — boost pages containing the active project name,
  key stakeholders, or feature names when they appear in the query
  - *Learn:* query-aware scoring signals

- [ ] **`/wiki search <query> --explain`** — print per-result: cosine score, BM25
  score, RRF rank, which signals fired
  - *Learn:* retrieval debugging; diagnosing why a relevant page ranked low

---

### Phase W5 — Dream Cycle (Overnight Enrichment)
*Goal: the wiki improves itself between sessions.*
*Inspired by GBrain's 66 cron jobs.*

- [ ] **Contradiction detector** — nightly: sample chunk pairs on the same topic;
  ask the model if they contradict; surface conflicts via `/wiki`
  - *Learn:* LLM-as-judge pattern; efficient pair sampling

- [ ] **Citation fixer** — verify facts that reference a session ID still have a
  live session in `memory.db`; mark orphaned facts
  - *Learn:* provenance tracking; referential integrity across two stores

- [ ] **Salience scorer** — nightly: re-score chunks by retrieval frequency; demote
  stale low-salience chunks in ranking
  - *Learn:* usage-based relevance signals; recency + access frequency as signals

- [ ] **Wire into `/wiki dream` manual trigger** (or a cron)
  - *Learn:* reactive (per-turn) vs. proactive (scheduled) memory maintenance

---

### Phase W6 — Schema & Typed Pages
*Goal: the wiki has structure, not just content.*
*Inspired by GBrain's schema packs and 22 typed page kinds.*

- [ ] **Page types** — taxonomy for product feature wikis:
  `decision`, `requirement`, `open-question`, `stakeholder`, `metric`, `risk`
  - Add `type:` to YAML frontmatter; enforce in `write_page`
  - *Learn:* why typed schemas improve extraction precision and retrieval routing

- [ ] **Type-aware extraction** — route extracted facts to the right page type
  ("we decided X" → `decisions/`, "the goal is Y" → `requirements/`)
  - *Learn:* classifier prompts; LLM routing vs. rule-based routing tradeoff

- [ ] **`/wiki schema`** — list page types, counts per type, untyped pages
  - *Learn:* schema introspection; auditing knowledge base coverage