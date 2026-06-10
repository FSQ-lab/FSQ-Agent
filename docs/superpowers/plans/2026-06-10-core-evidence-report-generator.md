# Core Evidence Report Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a report-layer generator that converts one deterministic core `evidence-manifest.json` into Markdown and JSON reports.

**Architecture:** Keep existing agent `ReportGenerator` intact. Add `CoreEvidenceReportGenerator` in `fsq_agent.report` that reads persisted evidence manifests, summarizes step statuses, failures, events, and artifacts, writes `core-report.md/json` next to the manifest, and returns the existing `ReportArtifact` model.

**Tech Stack:** Python, pytest, Pydantic `EvidenceBundle`, existing `ReportArtifact`, repository report module patterns.

---

### File Structure

- Modify: `fsq_agent/report/SPEC.md` to document the public API.
- Modify: `fsq_agent/report/__init__.py` to export `CoreEvidenceReportGenerator`.
- Create: `fsq_agent/report/_core_evidence_report.py` for implementation.
- Test: `tests/test_core_evidence_report.py`.

### Task 1: Write Failing Report Test

**Files:**
- Create: `tests/test_core_evidence_report.py`

- [x] **Step 1: Add manifest fixture and report assertions**

Create an `EvidenceBundle` with one passed step, one failed step, two events, and one artifact. Write it as `evidence-manifest.json`, call `CoreEvidenceReportGenerator().generate_from_manifest(manifest_path)`, and assert:

- returned artifact path is `core-report.md`
- JSON report path is `core-report.json`
- Markdown contains run id, status summary, failed step, failure category, and artifact path
- JSON contains `run_id`, `summary`, `steps`, `events`, and `artifacts`

- [x] **Step 2: Verify red**

Run: `pytest tests/test_core_evidence_report.py -q`

Expected: import error because `CoreEvidenceReportGenerator` does not exist yet.

### Task 2: Implement Generator

**Files:**
- Create: `fsq_agent/report/_core_evidence_report.py`
- Modify: `fsq_agent/report/__init__.py`

- [x] **Step 1: Implement manifest loading**

Read JSON, validate it with `EvidenceBundle.model_validate`, and preserve the manifest path.

- [x] **Step 2: Implement summary shape**

Compute:

```python
{
    "run_id": bundle.run_id,
    "status": "passed" | "failed",
    "step_count": len(bundle.steps),
    "passed_steps": ...,
    "failed_steps": ...,
    "artifact_count": len(bundle.artifacts),
}
```

- [x] **Step 3: Write Markdown and JSON**

Write `core-report.md` and `core-report.json` next to the manifest. The Markdown should include sections for summary, steps, failures, events, and artifacts.

- [x] **Step 4: Export generator**

Add `CoreEvidenceReportGenerator` to `fsq_agent.report.__all__`.

### Task 3: Verify And Commit

**Files:**
- Modified files from Tasks 1-2.

- [x] **Step 1: Run narrow and related tests**

Run: `pytest tests/test_core_evidence_report.py tests/test_report.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run: `pytest -q`

Expected: PASS.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 3: Commit**

Run:

```bash
git add fsq_agent/report/SPEC.md fsq_agent/report/__init__.py fsq_agent/report/_core_evidence_report.py tests/test_core_evidence_report.py docs/superpowers/plans/2026-06-10-core-evidence-report-generator.md
git commit -m "feat: add core evidence report generator"
```

### Self-Review

- Spec coverage: The plan implements the single-run core evidence report path described in report SPEC.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: The generator consumes existing `EvidenceBundle` and returns existing `ReportArtifact`; no shared model changes are needed.
