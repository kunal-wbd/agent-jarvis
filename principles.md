# Principles

Durable design rules for this harness, with the reasoning that produced them.

These are not aspirations. Each one came from something that broke, or from a design
question that had a non-obvious right answer. The *why* matters more than the rule —
a rule without its reasoning gets misapplied the first time a new situation looks
superficially similar.

Read this before starting work in a fresh session.

---

## Context and isolation

### P1 — Conversational state is isolated per agent; artifact state is shared per project

A conversation's `messages[]` is the isolation boundary. The project directory is the
shared surface. Agents that need independent judgment must not share message history.

**Why:** A reviewer conditioned on the author's reasoning is an echo, not a review. The
independence has to be structural, because there is no way to instruct a model to
"ignore what you just read."

**Not** multi-tenancy. Tenancy means isolating customers — separate credentials, no data
leakage. Here agents *must* share the project directory; that shared artifact space is
the mechanism by which a reviewer reviews anything. Agents are roles inside a project,
not peers of it.

### P2 — Four layers of context, four lifetimes

Touching one does not touch another.

| Layer | Lives in | Reset by |
|---|---|---|
| System prompt | `messages[0]` | `set_system_prompt()` |
| Conversation history | `messages[1:]` | Only a new conversation |
| Durable memory | `memory.db` | Never (append-only) |
| Artifacts | Files on disk | Manual edit only |

**Why:** Every "why didn't clearing X work?" question in v1 was a case of touching one
layer and assuming it touched another.

**Evidence:** `/clear-skills` rewrites `messages[0]` and cannot undo behaviour already
established in `messages[1:]` — the model keeps acting skill-shaped because recent turns
are a stronger behavioural signal than the system prompt. The `/resume` bug was the same
shape: the DB row lost its project because the in-memory object was reconstructed without
it.

### P3 — Distinguish persistent modes from scoped invocations

Modes layer instructions into an ongoing conversation and persist until cleared.
Invocations run in a fresh context from an explicit task brief, return an artifact, and
discard their working state.

**A persona swap on an existing conversation is not isolation.** Rewriting `messages[0]`
to a reviewer persona leaves the entire authoring conversation in `messages[1:]`.

**The test:** does this instruction shape an ongoing interaction, or execute a bounded
operation?

| Bounded → invocation | Ongoing → mode |
|---|---|
| Produce a .docx | "Be direct, no preamble" |
| Extract facts from transcripts | Draft a spec across twenty turns |
| Convert a PDF to markdown | Output conventions, file naming |

---

## Communication

### P4 — Agents communicate through durable artifacts, never through message history

**Why summaries are the wrong default:** a summary carries the summarizer's framing. A
reviewer reading the author's summary of the author's own work inherits the author's
judgment about what mattered — the same independence leak as sharing `messages[]`, just
laundered through a summarization step. More subtle, not less dangerous.

Artifacts do not have this problem. The spec file *is* the work product. Reviewing the
actual file is reviewing the thing; reviewing a summary is reviewing a claim about the thing.

Summaries are a **compression tactic under volume constraint** — 50 sessions will not fit
in context — not a hand-off protocol between agents.

### P5 — Rich in, thin out

A subagent receives generously and returns minimally.

```
IN:   session history, the skill, tool schemas    (thousands of tokens)
OUT:  artifact reference + one-line descriptor     (tens of tokens)
```

**Why:** the invoking conversation re-sends its entire history on every subsequent call.
One line versus a full generation transcript compounds across every turn that follows.

The return contract has exactly two outcomes: a **complete outcome**, or a **request for
more information**. Uncertainty is a legitimate return value, not a failure.

---

## Boundaries

### P6 — Isolation is achievable; atomicity is not

A scoped invocation can be prevented from polluting the caller's context. It cannot be
rolled back once it writes to disk.

**Avoid the word "transactional."** It implies rollback, which is not on offer over
filesystem side effects. What is on offer is context isolation. Naming it accurately
prevents designing against a guarantee that does not exist.

### P7 — A prompt instruction is a request; only tool code is a boundary

`## Active project: scope to PRD/checkout` is text the model usually obeys. But
`read_file`, `write_file`, and `list_dir` will open any path, because nothing in the tool
code checks.

If a constraint actually matters — security, correctness — enforce it in the tool. If it
is convenience, prompt text is fine. Decide which, deliberately, rather than assuming
prompt text is enforcement.

### P8 — Tools, skills, and sessions are different kinds of things

- **Tool** — a mechanical capability with no judgment. `read_file` does not know *why*.
- **Skill** — behavioural instruction layered onto a persona. *How* to use the capability.
- **Conversation** — the identity and memory boundary. *Who* is acting and what they remember.

**Evidence:** `_llm_ingest` broke because it tried to be a tool that also "reads the source
and extracts knowledge." A stdio subprocess has no model access — that is a skill's job. The
function returned `None` and crashed the client's result join.

**Corollary:** much of what feels like heavyweight skill text is really tool-work that has
not been extracted yet. "How to write a .docx" is a tool. "What belongs in a summary" is
the skill.

---

## Efficiency

### P9 — Scope context to need; better still, never load it

The strongest version is not "release the skill after use" — it is that the skill never
enters the primary context at all. Loading it into a subagent means there is nothing to
release, nothing to leak, and no window where it biases the primary conversation.

Release-after-use is damage control. Never-loading is prevention.

### P10 — Prefer delta over full reprocessing, and make the delta auditable

Delta detection answers *"what material am I working from?"* — an input-scoping decision
made **once, before generation starts**, not inside a revision loop where re-deriving the
input set wastes work and lets the input shift while the loop tries to converge.

- Targeted retrieval *inside* the loop is a different thing and is permitted.
- A fresh artifact is delta-with-an-empty-ledger — no special case.
- The regenerate-vs-patch threshold belongs in the same input-scoping step.

**Auditable** means a ledger records what was consumed into what, so "why did this page
change?" is answerable without diffing the whole corpus.

### P11 — Measure before optimising

The full message history, all tool schemas, and every active skill's markdown are re-sent
on every model call. Cost per call grows linearly with history; cumulative cost grows
quadratically per session.

Phoenix records `llm.token_count.prompt` per span. Look at real numbers before choosing a
mitigation. The same rule applies to the wiki: markdown and `list_dir` until directory
listing demonstrably stops working, then embeddings — empirically, not preemptively.

---

## Practice

### P12 — Reproduce before fixing; lock the fix with a test

**Why:** every real bug in v1 had an assumed root cause that turned out to be wrong.

- `/resume` losing its project — assumed a save bug, was actually object construction
- Sessions out of order — assumed correct, surfaced only by writing the test
- Phoenix `default` project — assumed `service.name`, was `openinference.project.name`
- "Tracing packages broken" — was an empty `.venv`, nothing to do with tracing

Confirm with a throwaway script first. Then write the test that fails on the old behaviour.
Writing the test found a second bug at least once.

### P13 — Degrade gracefully

Optional infrastructure must never take down the core loop. Tracing probes Phoenix once and
skips cleanly when it is down, instead of retry-spamming every span batch. A tool that fails
returns an error string rather than raising through the MCP handler.

### P14 — Small, reviewable, reversible changes — even solo

Every fix goes through its own branch and PR, even with self-merge. Unresolved issues get
written into `TODO.md` with *why* and *how to fix* — not silently patched, not silently
ignored. A future session needs the reasoning, not just the diff.

### P15 — See every layer, or you have not learned it

The premise of this project is refusing framework black boxes so the loop, the tool routing,
and the context assembly are all things you wrote and can point at.

The cost is owning every bug in it. That is the education, not a side effect of it.

---

## See also

- [`harness-v2-prd.md`](harness-v2-prd.md) — requirements derived from these principles
- [`architecture.md`](architecture.md) — how the current implementation works
- [`TODO.md`](TODO.md) — known gaps, each with reasoning and a fix path
