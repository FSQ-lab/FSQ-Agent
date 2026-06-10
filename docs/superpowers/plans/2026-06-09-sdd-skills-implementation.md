# SDD Skills Implementation Plan

> **For agentic workers:** Follow this plan against the approved design in `docs/superpowers/specs/2026-06-09-sdd-skills-design.md`. This project intentionally uses SDD, not TDD. Do not introduce Superpowers `writing-plans`, `executing-plans`, or mandatory TDD into the implemented workflow.

**Goal:** Add a reusable SDD skill set that initializes project specifications and agent entry points, then guides requirement clarification, SPEC updates, and diff-based implementation audit.

**Architecture:** The repository will hold one initialization skill and three workflow skills under `.github/skills/`. Root `SPEC.md` will carry project-level architecture, module navigation, and SDD hard gates. `CLAUDE.md` and `AGENTS.md` will be thin agent entry points that tell Claude and Codex/VS Code to read root `SPEC.md` and relevant module specs.

**Tech Stack:** Markdown skill files, repository instruction files, existing `.github/skills` layout.

---

## File Map

- Modify: `.github/skills/spec-driven/SKILL.md`
- Create: `.github/skills/sdd-init/SKILL.md`
- Create: `.github/skills/requirements-to-design/SKILL.md`
- Create: `.github/skills/spec-implementation-audit/SKILL.md`
- Create: `SPEC.md`
- Modify: `CLAUDE.md`
- Create: `AGENTS.md`

## Task 1: Generalize `spec-driven`

**Files:**
- Modify: `.github/skills/spec-driven/SKILL.md`

- [ ] Read the approved design document and the current `spec-driven` skill.
- [ ] Preserve the existing four principles: design-first, SPEC as truth source, module boundary discipline, and change synchronization.
- [ ] Add an explicit input path for confirmed design documents from `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
- [ ] Clarify that design documents are inputs to SPEC updates, not implementation authorities.
- [ ] Replace `CLAUDE.md` navigation language with root `SPEC.md` navigation language.
- [ ] Keep existing project-specific guidance that still applies to FSQ-Agent, including module DAG synchronization.
- [ ] Verify the skill still says implementation cannot start until relevant `SPEC.md` files are reviewed and confirmed.

**Verification:**
- Read the final skill and confirm it covers every `spec-driven` requirement from the approved design.
- Confirm it does not introduce TDD or implementation-plan-driven development.

## Task 2: Add `requirements-to-design`

**Files:**
- Create: `.github/skills/requirements-to-design/SKILL.md`

- [ ] Create a skill with frontmatter `name: requirements-to-design`.
- [ ] Use a trigger description for unclear requirements, feature ideas, behavior changes, or non-trivial development before SPEC changes.
- [ ] Adapt Superpowers `brainstorming` front-half behavior: explore context, ask one question at a time, decompose broad scope, compare 2-3 approaches, present design sections, and write a design document.
- [ ] Require design documents to be saved under `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
- [ ] Include a design self-review checklist for placeholders, contradictions, ambiguous wording, and scope creep.
- [ ] Require user review of the written design document before proceeding.
- [ ] Replace Superpowers' terminal handoff to `writing-plans` with a handoff to `spec-driven`.
- [ ] State that the design document is not the implementation source of truth.

**Verification:**
- Confirm the skill does not instruct agents to implement code.
- Confirm it does not require TDD, `writing-plans`, or Superpowers execution skills.

## Task 3: Add `spec-implementation-audit`

**Files:**
- Create: `.github/skills/spec-implementation-audit/SKILL.md`

- [ ] Create a skill with frontmatter `name: spec-implementation-audit`.
- [ ] Define when to use it: after implementation, before completion claims, before merge/PR, or after fixing audit gaps.
- [ ] Require independent reviewer context when available.
- [ ] Limit reviewer inputs to relevant `SPEC.md` files, worktree diff or commit range, and minimal project navigation instructions.
- [ ] Explicitly reject implementation summaries, conversation history, passing tests alone, keyword scans alone, and design documents as final proof.
- [ ] Require output in the form `SPEC item -> diff evidence -> verdict`.
- [ ] Include verdicts: `implemented`, `incomplete`, `missing`, `diverged`, `documentation-only`, `interface-only`, `mock-or-stub`, and `needs-human-decision`.
- [ ] State that blocking gaps prevent completion claims and require either implementation fixes or a return to `spec-driven`.
- [ ] Preserve the Superpowers ordering idea: spec compliance audit comes before code quality review.

**Verification:**
- Confirm the audit is diff-based and SPEC-centered.
- Confirm tests are described only as auxiliary evidence, not replacement proof.

## Task 4: Add `sdd-init`

**Files:**
- Create: `.github/skills/sdd-init/SKILL.md`

- [ ] Create a skill with frontmatter `name: sdd-init`.
- [ ] Define it as a bootstrap skill, not a daily development workflow.
- [ ] Require it to install or update the three workflow skills under `.github/skills/`.
- [ ] Require it to create or update root `SPEC.md` as the project-level specification.
- [ ] Require it to update both `CLAUDE.md` and `AGENTS.md` as thin agent entry points.
- [ ] Specify that existing project specification content in `CLAUDE.md` should be migrated to root `SPEC.md` when root `SPEC.md` is absent.
- [ ] Specify that existing project content must be preserved and only clearly marked SDD sections should be inserted or updated.
- [ ] Specify conflict behavior: if existing project instructions conflict with SDD gates, stop and ask the user.
- [ ] Include the exact hard gates from the approved design.
- [ ] State that only Claude and Codex/VS Code instruction entry points are supported for now.

**Verification:**
- Confirm `sdd-init` does not duplicate all details from the three workflow skills.
- Confirm it creates/updates root `SPEC.md` and points `CLAUDE.md` and `AGENTS.md` to it.
- Confirm it does not mention unsupported files such as `GEMINI.md` or `.cursorrules`.

## Task 5: Migrate project guide to root `SPEC.md` and thin agent entry points

**Files:**
- Create: `SPEC.md`
- Modify: `CLAUDE.md`
- Create: `AGENTS.md`

- [ ] Create root `SPEC.md` by migrating the current project specification content from `CLAUDE.md`.
- [ ] Preserve the existing FSQ-Agent module table, architecture diagram, and development rules in root `SPEC.md`.
- [ ] Add or update a `## Spec-Driven Development Workflow` section in root `SPEC.md`.
- [ ] Replace `CLAUDE.md` with a thin Claude entry point that says root `SPEC.md` is the project specification and module-level `SPEC.md` files must be read before changes.
- [ ] Create `AGENTS.md` with the same thin pointer for Codex / VS Code Codex.
- [ ] Include these hard gates exactly in substance:

```text
For non-trivial development:
1. Clarify requirements and produce a design document.
2. Update or create relevant module SPEC.md files from that design.
3. Get SPEC.md confirmation before implementation.
4. Implement only against confirmed SPEC.md.
5. If implementation reveals missing design, stop and update SPEC.md first.
6. Before claiming completion, run independent diff-based SPEC implementation audit.
```

- [ ] Clarify the bugfix shortcut: bug fixes that do not change public interfaces or intended behavior may skip design documents, but must still read relevant `SPEC.md` files and verify they remain accurate.

**Verification:**
- Confirm root `SPEC.md` contains the module table, architecture diagram, development rules, and SDD workflow section.
- Confirm `CLAUDE.md` and `AGENTS.md` are thin pointers and do not duplicate the project specification.
- Confirm no file contradicts the existing module-specific SPEC rules.

## Task 6: Final SPEC implementation audit for the skill work

**Files:**
- Read: `docs/superpowers/specs/2026-06-09-sdd-skills-design.md`
- Review diff for all files changed by this plan.

- [ ] Run `git diff -- .github/skills SPEC.md CLAUDE.md AGENTS.md`.
- [ ] Audit the diff against the approved design document.
- [ ] Produce a table mapping design requirements to diff evidence and verdicts.
- [ ] Fix any `missing`, `incomplete`, `diverged`, `documentation-only`, `interface-only`, or `mock-or-stub` findings.
- [ ] Re-run the audit after fixes.

**Verification:**
- Completion can be claimed only after every blocking design requirement has `implemented` or an explicitly accepted `needs-human-decision` verdict.
