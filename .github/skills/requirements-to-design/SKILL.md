---
name: requirements-to-design
description: Use when requirements are unclear, a feature or behavior change is requested, or non-trivial development needs a confirmed design before SPEC.md changes.
user-invocable: true
argument-hint: "[idea, feature request, or problem statement]"
---

# Requirements To Design

Use this skill to turn an idea into a reviewed design document. This is the SDD front end. It clarifies intent and records design decisions, but it does not update `SPEC.md` files and does not implement code.

## Hard Gate

Do not write implementation code during this skill. Do not update module `SPEC.md` files during this skill unless the user explicitly switches to `spec-driven`.

The terminal state is a confirmed design document and a handoff to `spec-driven`.

## Process

### 1. Explore project context

Read enough local context to understand the existing project shape before asking detailed questions:

- Root `SPEC.md` when present.
- Relevant module `SPEC.md` files when the affected area is obvious.
- Existing docs, recent commits, or project instructions when useful.

If no root `SPEC.md` exists yet, note that `sdd-init` may be needed before implementation.

### 2. Check scope

If the request spans multiple independent subsystems, stop and propose decomposition. Each independent subsystem should get its own design document and later its own SPEC update cycle.

### 3. Ask clarifying questions

Ask one question at a time. Prefer multiple choice when it helps the user answer quickly. Focus on:

- Goal and success criteria.
- User-visible behavior.
- Constraints and non-goals.
- Affected modules or ownership boundaries.
- Risks, edge cases, and rollout concerns.

### 4. Propose approaches

Present 2-3 approaches with trade-offs and a recommendation. Keep the recommendation explicit, but let the user choose or revise.

### 5. Present the design in sections

Present the design in reviewable sections scaled to complexity. Cover what applies:

- Purpose and scope.
- Architecture and module ownership.
- Data or control flow.
- Public behavior and interfaces.
- Error handling and edge cases.
- Verification and audit expectations.

Ask for confirmation after each meaningful section. Revise until the user approves the design.

### 6. Write the design document

Save the confirmed design to:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

The document should include:

- Goal.
- Scope and non-goals.
- Proposed design.
- Affected root/module specs expected to change.
- Open questions resolved during discussion.
- Verification expectations.

### 7. Self-review the design document

Before handoff, check and fix:

- Placeholder text such as `TBD`, `TODO`, or vague promises.
- Internal contradictions.
- Scope that is too broad for one SPEC update cycle.
- Ambiguous requirements that could be implemented two different ways.
- Hidden implementation assumptions that should be made explicit.

### 8. User review gate

Ask the user to review the written design document. Do not proceed until the user confirms it.

### 9. Handoff

After confirmation, invoke or instruct use of `spec-driven` with the design document path. The next step is to translate the design into root/module `SPEC.md` updates.

## Boundaries

- The design document is not the implementation source of truth.
- After `SPEC.md` files are updated and confirmed, implementation must follow `SPEC.md`, not this design document.
- Do not invoke Superpowers `writing-plans` as the next step.
- Do not require TDD.
- Do not start implementation from the design document.

## Output Shape

End with:

```text
Design document: docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
Next step: use spec-driven to update root/module SPEC.md files from this design.
```
