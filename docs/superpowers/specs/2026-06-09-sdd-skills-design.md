# SDD Skills Design

## Goal

Design a reusable set of Spec-Driven Development (SDD) skills that helps AI agents and human collaborators do vibe coding without drifting away from an explicit specification workflow.

The skills must make the development loop center on `SPEC.md` files:

1. Clarify requirements before changing specs or code.
2. Capture the clarified design in a design document.
3. Convert the design document into module `SPEC.md` changes.
4. Implement only against confirmed `SPEC.md` files.
5. Audit the implementation against `SPEC.md` and the worktree diff before claiming completion.

## Skill Set

The reusable SDD package contains one initialization skill and three daily workflow skills.

```text
sdd-init
requirements-to-design
spec-driven
spec-implementation-audit
```

### `sdd-init`

`sdd-init` is a project bootstrap skill, not a daily development workflow. It installs or updates the SDD workflow instructions for a repository.

It supports two agent entry points:

```text
CLAUDE.md  # Claude / Claude Code project instructions
AGENTS.md  # Codex / VS Code Codex durable repo instructions
```

It writes the same SDD hard gates into both files while preserving existing project guidance. If either file already has project-specific instructions, `sdd-init` should update only a clearly marked SDD workflow section. If existing instructions conflict with the SDD gates, it must stop and ask the user to choose the intended policy.

It also installs or updates the project skills:

```text
.github/skills/requirements-to-design/SKILL.md
.github/skills/spec-driven/SKILL.md
.github/skills/spec-implementation-audit/SKILL.md
```

### `requirements-to-design`

`requirements-to-design` adapts the useful front half of Superpowers `brainstorming` for SDD.

It should:

- Explore current project context before proposing designs.
- Ask clarifying questions one at a time.
- Decompose work that is too broad for one design.
- Present 2-3 approaches with trade-offs and a recommendation.
- Present the chosen design in reviewable sections.
- Write the confirmed design to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
- Self-review the design document for placeholders, contradictions, unclear scope, and ambiguity.
- Ask the user to review the design document before proceeding.

It must not:

- Start implementation.
- Invoke or require TDD.
- Invoke Superpowers `writing-plans` as the next step.
- Treat the design document as the implementation source of truth.

The design document is an input to `spec-driven`; it is not a substitute for module `SPEC.md` files.

### `spec-driven`

`spec-driven` is the SDD middle layer. It converts confirmed design intent into module specifications and enforces module boundaries.

It is based on the current project skill at `.github/skills/spec-driven/SKILL.md`, generalized for reuse across projects.

It should preserve these principles:

- `SPEC.md` is the single source of truth for implementation.
- Implementation must not start until the relevant `SPEC.md` files are reviewed and confirmed.
- Every module has one `SPEC.md` with a consistent structure.
- Public symbols are exported only from module entry points such as `__init__.py`, using explicit public API declarations where applicable.
- Internal implementation files stay internal.
- Shared data structures and exceptions live in the project-designated shared model module when the project has one.
- Module dependencies must follow the project dependency graph.
- SPEC/code synchronization must be checked after implementation.

It should add one explicit input path:

- When a confirmed design document exists, read it first and translate it into affected module `SPEC.md` changes.

Once `SPEC.md` files are confirmed, implementation must use those `SPEC.md` files as the authority. If implementation reveals missing or wrong design, the agent must stop and return to `spec-driven` to update the relevant `SPEC.md` before continuing.

### `spec-implementation-audit`

`spec-implementation-audit` is the SDD completion gate. It adapts Superpowers review ideas into an independent diff-based audit.

It should use a fresh reviewer or independent context whenever the platform supports it. The reviewer input is limited to:

- Relevant module `SPEC.md` files.
- The worktree diff or commit range being audited.
- Minimal project navigation instructions needed to locate modules and public APIs.

It must not rely on:

- The implementation agent's summary.
- Conversation history.
- Tests passing by themselves.
- Keyword scans by themselves.
- A design document as the final authority.

The audit output must map specification items to evidence from the diff:

```text
SPEC item -> diff evidence -> verdict
```

Supported verdicts should include:

- `implemented`
- `incomplete`
- `missing`
- `diverged`
- `documentation-only`
- `interface-only`
- `mock-or-stub`
- `needs-human-decision`

Blocking gaps prevent completion claims. The implementation agent must fix the code or return to `spec-driven` if the SPEC itself needs correction, then request another audit.

## Workflow Hard Gates

The SDD workflow installed by `sdd-init` should state these gates in `CLAUDE.md` and `AGENTS.md`:

```text
For non-trivial development:
1. Clarify requirements and produce a design document.
2. Update or create relevant module SPEC.md files from that design.
3. Get SPEC.md confirmation before implementation.
4. Implement only against confirmed SPEC.md.
5. If implementation reveals missing design, stop and update SPEC.md first.
6. Before claiming completion, run independent diff-based SPEC implementation audit.
```

Bug fixes may use a shorter path only when they do not change public interfaces or intended module behavior. Even then, the agent must read the relevant `SPEC.md`, fix the issue, and verify that `SPEC.md` remains accurate.

## Superpowers Fusion

The SDD skills should reuse selected Superpowers ideas without adopting the full Superpowers workflow.

Use from Superpowers:

- `brainstorming`: requirement clarification, option exploration, design section review, design document writing, and design self-review.
- `requesting-code-review`: independent reviewer context and severity-based issue handling.
- `subagent-driven-development`: the ordering idea that spec compliance review comes before code quality review.
- `verification-before-completion`: evidence before completion claims.
- `writing-plans`: only the concepts of coverage self-review and no placeholders.

Do not adopt from Superpowers:

- Mandatory TDD.
- The `design doc -> implementation plan -> code` path.
- Superpowers `writing-plans` as the next step after design.
- Superpowers `executing-plans` as a required implementation path.
- Branch finishing, parallel-agent dispatch, or worktree management as core SDD requirements.

## Current Project Bootstrap Notes

The FSQ-Agent repository already has:

```text
.github/skills/spec-driven/SKILL.md
CLAUDE.md
docs/superpowers/specs/
```

It still needs, if this design is implemented here:

```text
AGENTS.md
.github/skills/sdd-init/SKILL.md
.github/skills/requirements-to-design/SKILL.md
.github/skills/spec-implementation-audit/SKILL.md
```

The existing `spec-driven` skill should be enhanced and generalized rather than replaced wholesale.

## Success Criteria

The resulting SDD skills are successful when an agent can enter a repository and consistently follow this flow:

```text
idea
  -> requirements-to-design
  -> design document
  -> spec-driven
  -> confirmed SPEC.md
  -> implementation
  -> spec-implementation-audit
  -> completion only if audit passes
```

They should prevent these common vibe coding failures:

- Starting implementation before the design is clear.
- Treating chat context as a durable specification.
- Updating code without updating `SPEC.md`.
- Implementing against a design document after `SPEC.md` exists.
- Claiming completion because tests passed while SPEC items are missing.
- Shipping interface declarations, mocks, stubs, or documentation-only changes as if they were full implementation.
