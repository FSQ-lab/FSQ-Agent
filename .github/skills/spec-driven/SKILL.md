---
name: spec-driven
description: Use when the user invokes spec-driven with an approved design path, asks to update SPEC.md files from a confirmed design, or wants Python SDD implementation run from confirmed specs.
---

# Spec-Driven Development

Translate approved design intent into root/module `SPEC.md` files, get confirmation, then carry the work through implementation, verification, synchronization, and audit. This is the main execution skill after `requirements-to-design`.

## Core Rule

`SPEC.md` files are the source of truth for implementation.

- Root `SPEC.md` owns repository-wide architecture, module navigation, dependency diagrams, and global development rules.
- Module `SPEC.md` files own module contracts, public interfaces, internal structure, dependencies, error handling, testing contracts, and design decisions.
- `CLAUDE.md` and `AGENTS.md` are thin agent entry points only. They point agents to root `SPEC.md`; they are not specifications.

Implementation must not start until relevant `SPEC.md` changes are reviewed and confirmed.

## Required Flow

Do not stop after updating `SPEC.md`. Once the user confirms the SPEC changes, continue in the same turn whenever feasible:

```text
approved design document
  -> update root/module SPEC.md
  -> user confirms SPEC.md changes
  -> implement against confirmed SPEC.md
  -> run verification
  -> run SPEC/code synchronization check
  -> run spec-implementation-audit
  -> fix blocking gaps or ask for decision
  -> final report
```

If the user invokes this with a task instead of a design path, identify whether an approved design already exists. If not and the change is non-trivial, stop and tell the user to invoke `requirements-to-design` first.

## Input Path

When a confirmed design document exists, read it before editing specs:

```text
docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md
```

The design document is input to SPEC updates, not implementation authority. Once `SPEC.md` is confirmed, code must be implemented against `SPEC.md`.

## Python Architecture Integration

For Python projects or Python modules, apply the sibling `python-architecture` rules layer before:

- Choosing module ownership.
- Writing or updating module `SPEC.md` files.
- Implementing code.
- Running the synchronization and audit checks.

When this bundle is installed under `.github/skills/`, the references are expected at:

```text
.github/skills/python-architecture/SKILL.md
.github/skills/python-architecture/references/architecture-levels.md
.github/skills/python-architecture/references/module-spec-template.md
.github/skills/python-architecture/references/implementation-rules.md
.github/skills/python-architecture/references/audit-checklist.md
```

Load only the reference needed for the current phase:

- SPEC design or module ownership: `architecture-levels.md` and `module-spec-template.md`.
- Implementation: `implementation-rules.md`.
- Synchronization or audit: `audit-checklist.md`.

If the sibling files are unavailable, apply the local Python rules below and continue.

### Python Rules Summary

- Default to the simplest architecture level that satisfies the SPEC.
- Do not introduce Repository, Unit of Work, Service Layer, Clean Architecture, or DDD patterns without a SPEC-recorded reason.
- Public APIs are exported through module entry points such as `__init__.py`.
- Internal modules use the project convention, usually `_name.py`, and must not be imported across module boundaries.
- Domain logic must not depend on FastAPI, Django, Flask, SQLAlchemy sessions, HTTP request objects, or CLI argument parsers unless the module SPEC explicitly permits that coupling.
- Pydantic schemas, serializers, ORM models, and DTOs are boundary models unless the SPEC explicitly chooses a simpler combined model.

## SPEC Update Procedure

### New module or feature

1. Read root `SPEC.md` and relevant module `SPEC.md` files.
2. Read the confirmed design document.
3. Decide which module owns the feature, or whether a new module is needed.
4. For Python work, choose the Python architecture level and write the rationale into SPEC.
5. Write or update relevant module `SPEC.md` files.
6. If adding a module or changing module relationships, update root `SPEC.md` module table and architecture diagram.
7. Ask the user to confirm SPEC changes before implementation.
8. Implement only after confirmation.
9. Run verification, synchronization, and audit.

### Existing functionality change

1. Read root `SPEC.md` and current module specs for every touched module.
2. Read the confirmed design document when one exists.
3. Determine impact: public interface, module contract, internal-only, or cross-module dependency change.
4. Update relevant specs.
5. Ask the user to confirm SPEC changes before implementation.
6. Implement only after confirmation.
7. Run verification, synchronization, and audit.

### Narrow bug fix

Bug fixes that do not change public interfaces or intended behavior may skip design-doc creation. Still read relevant specs, fix code, verify specs remain accurate, and update specs only if the bug reveals inaccurate or incomplete specification.

## Module SPEC Structure

Every module has exactly one `SPEC.md`. Use this structure unless root `SPEC.md` defines a compatible local convention:

```text
# Module: {name}
## Purpose
## Dependencies
## Public Interface
## Internal Structure
## Python Architecture        (for Python modules)
## Error Handling             (if applicable)
## Testing Contract
## Design Decisions
```

Root `SPEC.md` should contain repository-wide sections such as:

```text
# {project} Project Specification
## Spec-Driven Development Workflow
## Module Table
## Architecture Diagram
## Development Rules
## Python Architecture Rules   (for Python repositories)
```

## Implementation Rules

After SPEC confirmation:

1. Re-read confirmed root/module specs.
2. Implement only what the confirmed specs require.
3. If implementation reveals a missing or wrong SPEC decision, stop and update SPEC first.
4. Keep edits scoped to affected modules and tests.
5. For behavior changes, write or update tests before production code unless the user explicitly accepts a generated-code or throwaway exception.
6. Run the repository's available verification commands.

## Change Synchronization Check

After implementation, verify relevant specs still match code:

- [ ] Root `SPEC.md` module table matches actual modules.
- [ ] Root `SPEC.md` architecture diagram matches actual project dependencies.
- [ ] Module `SPEC.md` Public Interface matches exported public symbols.
- [ ] Module `SPEC.md` Dependencies match actual imports from other project modules.
- [ ] Module `SPEC.md` Internal Structure lists actual module files.
- [ ] Python Architecture section matches package layout, import direction, framework boundaries, and model boundaries.
- [ ] Agent entry files remain thin pointers to root `SPEC.md`.

If anything is out of sync, fix the spec or code before completion.

## Audit Gate

Before claiming completion, run the sibling `spec-implementation-audit` procedure or apply it directly. If available, read:

```text
.github/skills/spec-implementation-audit/SKILL.md
```

Audit against:

```text
root SPEC.md + relevant module SPEC.md files + actual diff
```

Tests, lint, and summaries are supporting evidence only. They do not replace diff-based SPEC audit.

If blocking gaps exist:

- Fix implementation gaps and re-audit.
- If SPEC and implementation cannot be reconciled, ask the user for a design decision.
- Do not claim completion while blocking gaps remain.

## Required Final Report

End with:

- Specs updated and confirmed.
- Files implemented.
- Verification commands run and results.
- Synchronization check result.
- Audit result, including any accepted human decisions.
