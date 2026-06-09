---
name: spec-driven
description: Use when translating an approved design into SPEC.md files, changing public behavior, adding modules, modifying module boundaries, or checking SPEC/code synchronization before implementation.
user-invocable: true
argument-hint: "[task or design document path]"
---

# Spec-Driven Development

Use this skill after requirements have been clarified and, for non-trivial work, a design document has been approved. This skill turns design intent into project and module specifications. It does not implement code.

## Core Rule

`SPEC.md` files are the source of truth for implementation:

- Root `SPEC.md` owns repository-wide architecture, module navigation, dependency diagrams, and global development rules.
- Module `SPEC.md` files own module contracts, public interfaces, internal structure, dependencies, error handling, and design decisions.
- `CLAUDE.md` and `AGENTS.md` are agent entry points only. They must point agents to root `SPEC.md`; they are not specifications.

Implementation must not start until the relevant root/module `SPEC.md` changes are reviewed and confirmed.

## Input Path

When a confirmed design document exists, read it before editing specs:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

The design document is an input to SPEC updates, not an implementation authority. Once `SPEC.md` is confirmed, code must be implemented against `SPEC.md`, not the design document or conversation history.

## Principle 1: Design First, Code Second

### New module or feature

1. Read root `SPEC.md` and any relevant module `SPEC.md` files.
2. Read the confirmed design document when one exists.
3. Decide which module owns the feature, or whether a new module is needed.
4. Write or update the relevant module `SPEC.md` files.
5. If adding a module or changing module relationships, update root `SPEC.md` module table and architecture diagram.
6. Get user confirmation on the SPEC changes before writing implementation code.
7. Implement only after confirmation.
8. Run the synchronization check.

### Modify existing functionality

1. Read root `SPEC.md` and the current `SPEC.md` for every module you will touch.
2. Read the confirmed design document when one exists.
3. Determine impact: public interface change, module contract change, internal-only change, or cross-module dependency change.
4. Update the relevant `SPEC.md` files to reflect the intended change.
5. Get user confirmation before modifying implementation code.
6. Implement only after confirmation.
7. Run the synchronization check.

### Bug fix that does not change public interfaces or intended behavior

1. Read root `SPEC.md` and the relevant module `SPEC.md` files.
2. Fix the code.
3. Verify the relevant `SPEC.md` files are still accurate after the fix.
4. Update specs only if the bug reveals inaccurate or incomplete specification.

## What Is Forbidden

- Writing implementation code and then backfilling `SPEC.md` afterward.
- Treating a design document, chat transcript, implementation plan, or test result as the source of truth after `SPEC.md` exists.
- Starting implementation before relevant `SPEC.md` files are confirmed, except for narrow bug fixes that do not change public interfaces or intended behavior.
- Updating `CLAUDE.md` or `AGENTS.md` as if they were project specifications.

## SPEC Structure

Every module has exactly one `SPEC.md`. It contains these sections in order unless the project root `SPEC.md` defines a compatible local convention:

```text
# Module: {name}
## Purpose
## Dependencies
## Public Interface
## Internal Structure
## Error Handling        (if applicable)
## Design Decisions
```

Root `SPEC.md` should contain repository-wide sections such as:

```text
# {project} Project Specification
## Spec-Driven Development Workflow
## Module Table
## Architecture Diagram
## Development Rules
```

## Module Boundary Discipline

1. Each module is a directory with a public entry point such as `__init__.py` when the project uses package modules.
2. Public API surface is exported only from the module entry point, using explicit public declarations where applicable.
3. Internal implementation files follow the project's internal-file convention, such as prefixing files with `_`.
4. Shared data structures and exceptions live in the project-designated shared model module when the project has one.
5. Module dependencies must follow the DAG documented in root `SPEC.md`.
6. Cross-module interaction uses public exports only. Do not import another module's internal files.

## Change Synchronization

After implementation, verify all relevant specs still match code:

- [ ] Root `SPEC.md` module table matches actual modules.
- [ ] Root `SPEC.md` architecture diagram matches actual project dependencies.
- [ ] Module `SPEC.md` Public Interface matches exported public symbols.
- [ ] Module `SPEC.md` Dependencies match actual imports from other project modules.
- [ ] Module `SPEC.md` Internal Structure lists actual files in the module directory.
- [ ] Agent entry files such as `CLAUDE.md` and `AGENTS.md` remain thin pointers to root `SPEC.md`.

If any item is out of sync, fix the spec or code before considering the task done.

## Workflow Summary

```text
requirements-to-design
  -> confirmed design document
  -> spec-driven updates root/module SPEC.md
  -> user confirms SPEC.md
  -> implementation
  -> synchronization check
  -> spec-implementation-audit
```

## Applying to `$ARGUMENTS`

Start by identifying whether `$ARGUMENTS` is a task description or a design document path. Then identify affected modules, read root `SPEC.md` and the relevant module specs, and follow the appropriate workflow branch above.
