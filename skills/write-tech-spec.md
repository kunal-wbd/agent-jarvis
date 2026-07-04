# Skill: Write Technical Spec

Use this skill when the user wants to translate product requirements into a
technical specification ready for engineering review.

## What to produce

Work through each section in order. Complete one section, confirm with the user,
then move to the next.

**Overview** — One paragraph. What is being built, why, and what it replaces or
extends. Not a restatement of the PRD — assume the reader has read it.

**Architecture** — How the system is structured. Include a component diagram in
plain text (ASCII or mermaid) if it helps. Call out where new components are
introduced vs. existing ones extended.

**Data model** — Tables, fields, types, constraints, and indexes that matter.
Note what is new vs. what already exists. Flag any schema migrations required.

**API contracts** — Endpoints or interfaces being added or changed. Include
method, path, request shape, response shape, and error codes. Be precise — this
is what engineers will implement against.

**Edge cases** — Enumerate the non-happy-path scenarios explicitly. Empty states,
rate limits, partial failures, concurrent writes, permission boundaries.

**Dependencies** — External services, internal systems, third-party libraries,
or data sources this feature relies on. Flag any that are not yet approved or
available.

**Risks** — What could go wrong, and what is the mitigation plan? Include
technical debt being introduced knowingly.

## Rules

- Do not skip sections. If a section does not apply, say so and why.
- API contracts must include at least one example request and response.
- Every risk must have a mitigation, even if the mitigation is "accepted risk — revisit post-launch."
