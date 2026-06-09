---
name: sdd-init
description: Use when initializing or migrating a repository to Spec-Driven Development with root SPEC.md, thin Claude/Codex instruction files, and SDD workflow skills.
user-invocable: true
argument-hint: "[repository or migration goal]"
---

# SDD Init

Use this bootstrap skill to install the reusable Spec-Driven Development workflow into a repository. This skill prepares project instructions and skills; it is not the daily development workflow.

## Scope

Supported instruction entry points:

```text
CLAUDE.md  # Claude / Claude Code
AGENTS.md  # Codex / VS Code Codex
```

Unsupported for now:

```text
GEMINI.md
.cursorrules
.github/copilot-instructions.md
other IDE-specific instruction files
```

## Target Structure

After initialization, the repository should have:

```text
SPEC.md
CLAUDE.md
AGENTS.md
.github/skills/requirements-to-design/SKILL.md
.github/skills/spec-driven/SKILL.md
.github/skills/spec-implementation-audit/SKILL.md
```

Root `SPEC.md` is the project-level specification. `CLAUDE.md` and `AGENTS.md` are thin entry points that tell agents to read root `SPEC.md` and relevant module specs.

## Procedure

### 1. Inspect existing instructions

Check for:

- Root `SPEC.md`.
- `CLAUDE.md`.
- `AGENTS.md`.
- Existing `.github/skills/` files.
- Existing project rules that conflict with SDD hard gates.

If a conflict exists, stop and ask the user which policy should win. Do not silently overwrite project rules.

### 2. Create or update root `SPEC.md`

If root `SPEC.md` does not exist and `CLAUDE.md` contains project specification content, migrate that content into root `SPEC.md`.

Root `SPEC.md` should include project-wide sections such as:

```text
# {project} Project Specification
## Spec-Driven Development Workflow
## Module Table
## Architecture Diagram
## Development Rules
```

Insert or update the SDD hard gates in root `SPEC.md`:

```text
For non-trivial development:
1. Clarify requirements and produce a design document.
2. Update or create relevant module SPEC.md files from that design.
3. Get SPEC.md confirmation before implementation.
4. Implement only against confirmed SPEC.md.
5. If implementation reveals missing design, stop and update SPEC.md first.
6. Before claiming completion, run independent diff-based SPEC implementation audit.
```

Bug fixes that do not change public interfaces or intended behavior may skip the design document, but must still read relevant `SPEC.md` files and verify that the specs remain accurate.

### 3. Create thin agent entry points

Replace or update `CLAUDE.md` and `AGENTS.md` so they point to root `SPEC.md` without duplicating the project specification.

Each entry point should state:

- This repository uses SDD.
- Root `SPEC.md` is the project-level source of truth.
- Relevant module `SPEC.md` files must be read before changes.
- Implementation must follow confirmed `SPEC.md` files.
- Completion requires independent diff-based SPEC implementation audit.

### 4. Install workflow skills

Install or update these skills under `.github/skills/`:

- `requirements-to-design`
- `spec-driven`
- `spec-implementation-audit`

Do not duplicate all workflow details in `sdd-init`; point to the dedicated skills.

### 5. Verify bootstrap

Confirm:

- Root `SPEC.md` exists and contains project-level guidance and SDD hard gates.
- `CLAUDE.md` is a thin pointer to root `SPEC.md`.
- `AGENTS.md` is a thin pointer to root `SPEC.md`.
- The three workflow skills exist under `.github/skills/`.
- No unsupported instruction files were modified.

## Daily Workflow After Init

For non-trivial work, agents should follow:

```text
requirements-to-design
  -> spec-driven
  -> implementation against confirmed SPEC.md
  -> spec-implementation-audit
```
