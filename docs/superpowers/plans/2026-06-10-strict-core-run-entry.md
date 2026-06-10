# Strict Core Run Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal strict FSQ core run helper that executes one YAML case, writes evidence, generates a core report, and keeps recovery separate.

**Architecture:** Reuse the existing `run_fsq_core_case` composition path for deterministic execution. Add `run_strict_fsq_core_case` in `fsq_agent.cli._core_execution` that calls the existing helper, requires the manifest path, invokes `CoreEvidenceReportGenerator`, and returns `ReportArtifact`. No platform construction, locator fallback, AI recovery, or testcase mutation is added.

**Tech Stack:** Python, pytest, existing CLI composition helper, `CoreEvidenceReportGenerator`, `ReportArtifact`.

---

### File Structure

- Modify: `fsq_agent/cli/SPEC.md`
- Modify: `fsq_agent/cli/_core_execution.py`
- Modify: `tests/test_cli_core_execution.py`
- Create: `docs/superpowers/plans/2026-06-10-strict-core-run-entry.md`

### Task 1: Write Failing Strict Entry Test

**Files:**
- Modify: `tests/test_cli_core_execution.py`

- [x] **Step 1: Add test**

Test `run_strict_fsq_core_case(...)` with the existing fake harness. Assert it writes:

- `evidence-manifest.json`
- `core-report.md`
- `core-report.json`

and returns `ReportArtifact` pointing to `core-report.md`.

- [x] **Step 2: Verify red**

Run: `pytest tests/test_cli_core_execution.py::test_run_strict_fsq_core_case_writes_evidence_and_core_report -q`

Expected: import error or missing function error for `run_strict_fsq_core_case`.

### Task 2: Implement Strict Entry

**Files:**
- Modify: `fsq_agent/cli/_core_execution.py`

- [x] **Step 1: Implement helper**

Add:

```python
def run_strict_fsq_core_case(... ) -> ReportArtifact:
    bundle = run_fsq_core_case(...)
    if bundle.manifest_path is None:
        raise ReportGenerationError("Strict core run did not produce an evidence manifest.", context={"run_id": run_id})
    return CoreEvidenceReportGenerator().generate_from_manifest(bundle.manifest_path)
```

- [x] **Step 2: Preserve existing behavior**

Keep `run_fsq_core_case` return type and behavior unchanged.

### Task 3: Verify And Commit

**Files:**
- Modified files from Tasks 1-2.

- [x] **Step 1: Run related tests**

Run: `pytest tests/test_cli_core_execution.py tests/test_core_evidence_report.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run: `pytest -q`

Expected: PASS.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 3: Commit**

Run:

```bash
git add fsq_agent/cli/SPEC.md fsq_agent/cli/_core_execution.py tests/test_cli_core_execution.py docs/superpowers/plans/2026-06-10-strict-core-run-entry.md
git commit -m "feat: add strict core run entry"
```

### Self-Review

- Spec coverage: The plan implements the strict entry described in CLI SPEC.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: The strict helper returns existing `ReportArtifact` and reuses existing `EvidenceBundle` manifest output.
