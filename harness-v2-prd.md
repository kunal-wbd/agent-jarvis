# Harness v2 — Product Requirements

**Status:** Draft
**Date:** 2026-07-28
**Author:** Kunal Lagwankar

---

## 1. Objective

Build a multi-agent harness — opencode/claude-code shaped — for incremental product
spec writing, with **learning the mechanics as the primary goal**. No agent frameworks
(LangGraph, CrewAI, Strands). Every layer is hand-written Python so the loop, the tool
routing, the context assembly, and the failure modes are all inspectable and modifiable.

All models run locally via Ollama. No cloud APIs.

v1 established a working single-agent loop. v2 is about **multi-agent architecture and
disciplined context management** — the two things v1 got wrong or left out.

---

## 2. What exists today

The starting point. v2 extends this rather than replacing it.

| Component | State |
|---|---|
| Agent loop | Working. `session/session.py:send()` — bounded by `MAX_TURNS`, yields typed events |
| Provider | `provider/ollama.py` — sole Ollama caller, normalises to `ModelResponse` |
| Tools | 3 backends via `tool/registry.py`: scripts (in-process), stdio (MCP subprocess), sse (placeholder) |
| Shipped tools | `read_file`, `write_file`, `list_dir`, `read_sessions`, `scrape_url` |
| Skills | `skills/*.md` injected into `messages[0]` via `/use`. Persistent only |
| Persistence | SQLite `memory.db` — `sessions` + `messages` tables, keyed by (date, project) |
| Tracing | OTEL → Arize Phoenix, `harness` project. Degrades gracefully when Phoenix is down |
| Project scoping | `PRD/<name>/` with `specs/`, `decisions/`, `acceptance-criteria/`. Auto-listed into prompt |
| REPL | `agent.py` — slash commands handled in Python, never reach the model |

**Known limitations v2 must address**, all documented in `TODO.md`:

- Full message history re-sent on every model call — token cost grows quadratically per session
- Skills are unconditionally persistent; `/clear-skills` only rewrites `messages[0]` and cannot
  undo behavioural residue in `messages[1:]`
- Path scoping is a prompt instruction, not enforced in tool code
- Tool inventory in `agents.md` is hand-maintained and drifts from `tool/registry.py:SCHEMAS`
- One `Session` holds exactly one agent's conversation — no mechanism for a second agent

---

## 3. Vocabulary

Precise terms, because v1's naming is part of what needs fixing.

**Project** — a unit of product work. Has a directory (`PRD/<name>/`), connected context
(specs, decisions, wiki), functionalities under development, and sessions spanning multiple days.
Projects are the outermost boundary; everything else is scoped inside one.

**Session** — a series of conversations, across one or more agents, working toward objectives
for a given project. Keyed by (project, date). A session is a *unit of work*, not a single
dialogue.

**Conversation** — a series of instructions, skills, prompts, and outcomes computed from tools
and LLMs. A conversation belongs to exactly one agent and may invoke subagents. This is the
unit that holds a `messages[]` list.

**Agent** — a persona (its own `agents/*.md`), operating within a project, holding its own
conversations. Agents do not share conversational state.

**Subagent** — a scoped invocation that runs in a fresh conversation, performs a bounded task,
returns an outcome, and discards its working context.

**Skill** — behavioural instruction (`skills/*.md`) layered into a conversation's system prompt.
Carries judgment: *what makes a good X*.

**Tool** — a mechanical capability with no judgment. Filesystem, HTTP, document conversion.

> **Naming migration:** v1's `Session` class is what v2 calls a **Conversation**. v2's
> **Session** is a new grouping layer above it. This is a schema change, not a rename —
> see §9.

---

## 4. Tenets

These are the durable conclusions. Requirements below derive from them.
Stated here in brief; [`principles.md`](principles.md) carries the full reasoning
and the v1 evidence behind each.

**T1 — Conversational state is isolated per agent; artifact state is shared per project.**
A conversation's `messages[]` is the isolation boundary. The project directory is the shared
surface. Agents that need independent judgment must not share message history.

**T2 — Agents communicate through durable artifacts, never through each other's message
history.** A summary carries the summarizer's framing, so it cannot be the input to a
judgment that must be independent. Summaries are a compression tactic under volume
constraint, not a hand-off protocol.

**T3 — Distinguish persistent modes from scoped invocations.** Modes layer instructions
into an ongoing conversation and persist until cleared. Invocations run in a fresh context
from an explicit task brief, return an artifact, and discard their working state. A persona
swap on an existing conversation is not isolation.

**T4 — Isolation is achievable; atomicity is not.** A scoped invocation can be prevented
from polluting the caller's context. It cannot be rolled back once it writes to disk.
Design side effects accordingly. Avoid the word "transactional".

**T5 — Scope context to need; release it when the need passes.** Better still, never load
it into the primary context at all. The test: *does this instruction shape an ongoing
interaction, or execute a bounded operation?* Ongoing → mode. Bounded → invocation.

**T6 — A prompt instruction is a request; only tool code is a boundary.** If a constraint
actually matters (security, correctness), enforce it in the tool. If it is convenience,
prompt text is fine — but decide which, deliberately.

**T7 — Four layers of context, four lifetimes.** Touching one does not touch another.

| Layer | Lives in | Reset by |
|---|---|---|
| System prompt | `messages[0]` | `set_system_prompt()` |
| Conversation history | `messages[1:]` | Only a new conversation |
| Durable memory | `memory.db` | Never (append-only) |
| Artifacts | Files on disk | Manual edit only |

**T8 — Reproduce before fixing; lock the fix with a test.** Every real bug in v1 had an
assumed root cause that was wrong. Confirm with a throwaway script first, then write the
test that fails on the old behaviour.

**T9 — Degrade gracefully.** Optional infrastructure (tracing, remote tools) must never
take down the core loop.

---

## 5. Requirements

### R1 — Multiple agents, isolated conversations

Support more than one agent persona operating within a project. Each agent has its own
`agents/<name>.md` and its own conversations. Two agents working the same project on the
same day must be independently addressable and independently resumable.

`AGENTS_MD_PATH` is already env-driven, so persona loading needs no new mechanism — the
gap is that `find_session(date, project)` returns one row with no notion of *which agent*.

### R2 — Artifact-based inter-agent communication

Agents exchange information by reading and writing files in the project directory. No agent
reads another's `messages[]`.

A reviewer agent reads the wiki, specs, and decisions as they exist on disk, and writes its
verdict as a new artifact (e.g. `decisions/review-<date>.md`) that other agents may later read.

### R3 — Skills: modes and invocations

Two distinct mechanisms, named distinctly.

**Persistent mode** — today's `/use <skill>`. Instructions layered into the system prompt,
active until cleared or the conversation ends. For collaborative, multi-turn work:
`write-tech-spec` while drafting across twenty turns.

**Scoped invocation** — new. The skill is loaded into a *subagent's* context and never enters
the invoking conversation. For bounded operations: generate a document, extract facts,
convert a format.

The mode/invocation choice is a property of the skill, declared in the skill file, not a
per-call decision by the user.

`/clear-skills` remains, with honest framing: it stops re-sending skill text on future calls
(a real token saving, and it prevents stacked skills from conflicting), but it cannot undo
behaviour already established in `messages[1:]`. A full reset requires a new conversation.

### R4 — Subagent invocation contract

Three properties, in priority order:

1. The subagent receives sufficient data to perform its role
2. It returns either a **complete outcome** or a **request for more information**
3. The invoking conversation absorbs only the outcome, never the working context

**Asymmetry is the efficiency win:**

```
IN:   rich  — session history, the skill, tool schemas    (thousands of tokens)
OUT:  thin  — artifact reference + one-line descriptor     (tens of tokens)
```

The return value is a path plus a short descriptor, so the invoker can reason about the
artifact without re-reading it:

```
specs/north-star-summary.docx — problem, goals, metrics, open questions as of 2026-07-28
```

The invoking conversation grows by one line rather than by a full generation transcript.
Because history is re-sent on every subsequent call, this compounds across every turn that
follows.

*How* the subagent obtains its input (copied from a live conversation, or read from the
durable store) is an implementation choice, not an architectural constraint.

### R5 — Self-correcting loop with an explicit objective

A subagent producing an artifact runs an internal loop that terminates on **quality**, not
on absence of tool calls:

```
draft → evaluate against objective → satisfactory? → return outcome
                                   → not satisfactory? → revise → evaluate
                                   → cannot satisfy?   → return needs-more-info
```

**The objective must be explicit and checkable**, or the loop degenerates into the model
approving its own first draft. "Write a good summary" is not an objective. "Cover problem,
goals, non-goals, open questions; every decision cites its source session; flag anything
unresolved" is.

Evaluation strategies, in ascending cost:

| Strategy | Catches | Cost |
|---|---|---|
| Mechanical checks | Missing sections, uncited claims, empty headings | No model call |
| Fresh-context critique | Weak arguments, judgment failures | One model call, isolated context |
| Independent reviewer agent | Whether the outcome serves the goal at all | Full agent invocation |

Self-critique *within the drafting context* is explicitly insufficient — the draft is present
in history as evidence of what "good" looks like, and the model will nearly always approve it.

Mechanical checks are the default: cheap, and they never rubber-stamp.

### R6 — Delta detection, outside the loop

Delta detection answers *"what material am I working from?"* — an input-scoping decision made
**once, before generation starts**. It must not sit inside the self-correction loop, where
re-deriving the input set every iteration wastes work and lets the input shift while the loop
is trying to converge.

```
[before]   delta detection → material set + prior artifact
                ↓
[loop]     draft → evaluate → revise → evaluate → …
                ↓
[after]    write artifact → update ledger
```

- **Targeted retrieval inside the loop is permitted and is a different thing.** If mid-revision
  the subagent needs context it did not load, fetching it is a read, not a re-scoping.
- **A fresh artifact is delta-with-an-empty-ledger.** No special case, no separate path — the
  first run finds nothing consumed, so the material set is everything.
- **Threshold decision, also outside the loop:** when the delta is large, regenerating beats
  incrementally patching. This belongs in the same input-scoping step that computed the delta.

The ledger records which sessions have been consumed into which artifact.

### R7 — Context efficiency

The full message history plus tool schemas plus all active skill text are re-sent on every
model call. Cost per call grows linearly with history; cumulative cost grows quadratically.

v2 must provide at least one mitigation. Candidates, not mutually exclusive:

- Skills as tools — the model calls `load_skill(name)` when it recognises a need; an unused
  skill costs one schema line instead of its full markdown body
- Sliding window over `messages[1:]`
- Periodic compression of older turns into a single summary message
- Dropping tool results beyond a recency threshold

Phoenix already records `llm.token_count.prompt` per span, so growth is measurable rather
than estimated. Measure before optimising.

### R8 — Project wiki

A structured, incrementally-built knowledge base per project, in markdown, readable and
editable by hand.

```
PRD/<project>/wiki/
    overview.md
    decisions/
    requirements/
    open-questions.md
    log.md          ← the ingestion ledger (R6)
```

Built by a `build-wiki` skill using the existing `read_sessions` tool. Retrieval is
`list_dir` + `read_file` — **no embeddings until directory listing demonstrably stops
working**. Reach for vector search empirically, not preemptively.

Update flow, per R6: read `log.md` → determine unconsumed sessions → read existing wiki
pages → extract from the delta only → merge against existing pages → write → update ledger.

Extract-then-merge, not batch-reprocess: batch reprocessing discards the value of computing
the delta at all, and lets a confused pass silently rewrite settled decisions.

**Open items the skill must specify explicitly**, or the model will improvise inconsistently:
- Contradiction handling — supersede, append, or flag for human resolution
- Page routing — what distinguishes a *decision* from a *requirement*, with examples

**Known gap:** sessions are mutable. A session already in `log.md` can grow. `read_sessions`
does not expose per-session `ended_at`, so nothing the model can see signals that a logged
session changed. Needs resolving before the ledger is trustworthy.

### R9 — Reviewer agent

An agent that independently judges outcome quality. Triggered manually (`/pm-review`) or on a
schedule. It reads the wiki, specs, and decisions from disk, judges them against the stated
objective, and writes a verdict artifact.

It must not share conversational state with the authoring agent — per T1, a reviewer
conditioned on the author's reasoning is an echo, not a review.

Because it may run with no live parent conversation, it must be able to operate purely from
durable state.

If triggered periodically, it needs delta detection (R6) — otherwise it re-reviews unchanged
material.

---

## 6. Non-goals

- Agent frameworks. The point is to build the mechanics.
- Cloud model APIs. Local Ollama only.
- Multi-user / multi-tenant isolation. Single operator. Agents are roles, not tenants.
- Atomicity or rollback of subagent side effects (T4).
- Vector search until listing-based retrieval demonstrably fails (R8).
- Full graph-based orchestration. Two agents with one conditional edge is a function, not a
  graph. Revisit when a third role with genuinely branching paths appears.

---

## 7. Open questions

1. **Session/Conversation schema migration** — v1's `Session` becomes v2's `Conversation`,
   with a new `Session` grouping layer. `messages.session_id` → `messages.conversation_id`,
   plus a `conversations` table carrying an `agent` column. When, and with what migration path
   for existing rows?
2. **Mutable-session delta detection** (R8) — what signal tells the wiki that an
   already-ingested session has grown?
3. **Skill declaration format** — how does a skill file declare mode vs. invocation?
4. **Subagent trigger for the reviewer** — manual, scheduled, or both? Affects whether delta
   detection is mandatory at v2 or deferred.
5. **Path enforcement** (T6) — does the stdio server become project-aware, or is a project
   root threaded through each call?

---

## 8. Success criteria

v2 is done when:

- [ ] Two agents with different personas operate on one project without sharing message history
- [ ] A subagent generates a document and the invoking conversation grows by one line, not a transcript
- [ ] A skill exists that never enters the primary context
- [ ] `/wiki update` builds pages from unconsumed sessions only, and the ledger proves it
- [ ] A reviewer agent produces a verdict artifact from durable state alone
- [ ] Token growth per session is measured in Phoenix, and one mitigation is in place
- [ ] Every requirement above has a test that fails on the v1 behaviour

---

## 9. Sequencing

Ordered by dependency, not by value.

1. **Schema: Session/Conversation split** — everything multi-agent depends on it
2. **Subagent invocation contract (R4)** — the primitive the rest builds on
3. **Skills: mode vs. invocation (R3)** — needs R4
4. **Wiki with delta ledger (R6, R8)** — first real consumer of R4 + R5
5. **Reviewer agent (R9)** — first real consumer of R1 + R2
6. **Context efficiency (R7)** — measure first; optimise once there is something to measure
