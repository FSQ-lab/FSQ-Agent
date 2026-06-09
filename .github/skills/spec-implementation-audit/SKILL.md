---
name: spec-implementation-audit
description: Use after implementation and before completion claims, merge, or PR when work must be checked against confirmed SPEC.md files and the actual diff.
user-invocable: true
argument-hint: "[diff range, task summary, or affected specs]"
---

# SPEC Implementation Audit

Use this skill to determine whether implementation truly satisfies confirmed specifications. This is a SPEC-centered, diff-based audit. It is not a general test pass check and not a restatement of the implementer's summary.

## Core Rule

Completion cannot be claimed until the implementation is audited against:

```text
root SPEC.md + relevant module SPEC.md files + worktree diff or commit diff
```

Tests, lint, keyword scans, and implementation summaries are auxiliary evidence only. They do not replace diff-based SPEC audit.

## Independence Requirement

Use a fresh reviewer or independent context whenever the platform supports it. The reviewer must not inherit the implementation agent's conversation history or rely on its self-report.

Reviewer input is limited to:

- Root `SPEC.md`.
- Relevant module `SPEC.md` files.
- Worktree diff or commit range.
- Minimal project navigation instructions required to locate modules and public APIs.
- Optional verification command outputs as auxiliary evidence.

Do not provide the reviewer with persuasive summaries such as "this is complete" or "tests pass, so it should be fine."

## Audit Procedure

1. Identify the SPEC items that apply to the change.
2. Read the diff and locate concrete implementation evidence for each SPEC item.
3. Classify each item with a verdict.
4. Report blocking gaps before any quality/style feedback.
5. If blocking gaps exist, return to implementation or to `spec-driven` when the SPEC itself needs correction.
6. Re-audit after fixes.

## Verdicts

Use these verdicts:

- `implemented`: Diff contains concrete implementation satisfying the SPEC item.
- `incomplete`: Diff partially implements the SPEC item but leaves required behavior uncovered.
- `missing`: No meaningful implementation evidence exists in the diff.
- `diverged`: Implementation contradicts the SPEC item.
- `documentation-only`: Diff changes docs/specs but not the required implementation.
- `interface-only`: Diff exposes signatures, exports, config, or declarations without required behavior.
- `mock-or-stub`: Diff uses placeholders, hardcoded responses, fake paths, or non-production behavior in place of required implementation.
- `needs-human-decision`: SPEC and implementation cannot be reconciled without a product or design decision.

Any verdict except `implemented` is blocking unless the user explicitly accepts `needs-human-decision` as out of scope for the current change.

## Required Output

Produce a table or structured list in this shape:

```text
SPEC item | Diff evidence | Verdict | Notes
```

Each diff evidence entry must cite concrete files and, when possible, line numbers or changed symbols. If evidence is absent, say so directly.

## What Not To Accept

- "The tests pass" as proof that a SPEC item is implemented.
- "The implementation agent said it handled this" as proof.
- A keyword search as proof without reading the changed code path.
- A design document as the final authority after `SPEC.md` exists.
- Public API declarations without backing behavior.
- Mocks, stubs, hardcoded success paths, or placeholder fallbacks as production implementation.

## Ordering

SPEC compliance comes before code quality review. If the implementation does not satisfy the SPEC, style and refactoring feedback are secondary.

## Completion Gate

Before claiming completion, state:

- Which root/module `SPEC.md` files were audited.
- Which diff or commit range was audited.
- Whether every blocking SPEC item is `implemented`.
- Any remaining `needs-human-decision` items accepted by the user.

If blocking gaps remain, do not claim completion.
