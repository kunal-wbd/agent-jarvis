# Skill: Write Acceptance Criteria

Use this skill when the user wants to convert a technical spec or PRD into
testable acceptance criteria.

## What to produce

A numbered list of Given/When/Then statements that a QA engineer or developer
could use to verify the feature is complete and correct.

Format each criterion as:

```
N. Given <precondition>
   When <action or event>
   Then <expected outcome>
```

## Coverage checklist

Before finalizing, verify criteria cover:

- Happy path — the primary intended flow
- Validation errors — missing fields, wrong types, out-of-range values
- Permission boundaries — who can and cannot take this action
- Empty / zero state — what happens when there is no data
- Concurrent or repeated actions — what happens if triggered twice
- Failure recovery — what the system does when a dependency is unavailable

## Rules

- Each criterion tests exactly one thing. If "and" appears in the Then clause,
  split it into two criteria.
- Outcomes must be observable — a state change, a response, a UI update, a log
  entry. "The system handles it" is not a valid Then.
- Number criteria sequentially. Group by feature area with a plain-text header
  if there are more than eight.
