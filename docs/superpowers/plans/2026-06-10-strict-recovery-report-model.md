# Strict Recovery Report Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record the strict-regression and recovery-report design so future implementation keeps original testcase failures separate from recovery attempts.

**Architecture:** This batch is documentation/specification only. `core` defines strict execution boundaries, `report` defines future report surfaces, and a design document explains the two-phase regression model. Runtime code and shared models are intentionally deferred until the public contracts are reviewed.

**Tech Stack:** Markdown specs under `docs/superpowers/specs`, module `SPEC.md` files, existing git workflow.

---

### File Structure

- Create: `docs/superpowers/specs/2026-06-10-strict-recovery-report-design.md`
- Modify: `fsq_agent/report/SPEC.md`
- Modify: `fsq_agent/core/SPEC.md`

### Task 1: Write Strict/Recovery Design Document

**Files:**
- Create: `docs/superpowers/specs/2026-06-10-strict-recovery-report-design.md`

- [x] **Step 1: Define execution phases**

Document strict regression run and recovery run as separate phases. Strict run executes YAML exactly as authored without AI, fallback, or testcase mutation. Recovery run consumes strict failure evidence and may attempt deterministic or later AI-assisted repair.

- [x] **Step 2: Define final classifications**

Document `strict_passed`, `strict_failed_recovery_passed`, `strict_failed_recovery_failed`, and `strict_failed_recovery_not_attempted`.

- [x] **Step 3: Define report shape and ownership**

Document single-run core evidence reports, strict/recovery comparison reports, and the ownership rule that report layout belongs in `report`, not in runner/harness/driver/evidence code.

### Task 2: Update Report SPEC

**Files:**
- Modify: `fsq_agent/report/SPEC.md`

- [x] **Step 1: Add planned report support**

Add planned support for single-run core evidence reports and strict-vs-recovery comparison reports.

- [x] **Step 2: Add future module names**

Add future `_core_evidence_report.py` and `_regression_report.py` responsibilities.

- [x] **Step 3: Add design decision**

Record that comparison reports are generated from persisted manifests so recovery cannot mask original regression signal.

### Task 3: Update Core SPEC

**Files:**
- Modify: `fsq_agent/core/SPEC.md`

- [x] **Step 1: Clarify strict default**

Document that the deterministic core path is strict by default and does not silently apply locator fallback or AI recovery.

- [x] **Step 2: Clarify recovery boundary**

Document that deterministic fallback or AI-assisted repair must be invoked as a separate recovery run with separate evidence.

### Task 4: Verify And Commit

**Files:**
- Modified files from Tasks 1-3.

- [x] **Step 1: Run diff check**

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 2: Commit**

Run:

```bash
git add docs/superpowers/specs/2026-06-10-strict-recovery-report-design.md docs/superpowers/plans/2026-06-10-strict-recovery-report-model.md fsq_agent/report/SPEC.md fsq_agent/core/SPEC.md
git commit -m "docs: define strict recovery report model"
```

### Self-Review

- Spec coverage: The plan records execution phases, report classifications, ownership boundaries, and future implementation order.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: No new runtime types are introduced in this documentation batch.
