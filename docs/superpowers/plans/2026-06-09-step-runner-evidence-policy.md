# Step Runner Evidence Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `StepRunner` own evidence-policy capture timing and attach captured artifact references to phase reports and runner events.

**Architecture:** `StepRunner` will inspect `ExecutableStep.evidence_policy` and call `HarnessInterface.capture_artifact` during prepare/finalize/failure paths. Harnesses remain raw capture adapters; `ArtifactStore` still owns paths; `EvidenceRecorder` consumes the resulting phase reports and events.

**Tech Stack:** Python 3, Pydantic shared models, pytest.

---

### Task 1: Before/After Artifact Capture

**Files:**
- Modify: `tests/test_step_runner.py`
- Modify: `fsq_agent/core/runner/_runner.py`

- [x] **Step 1: Write failing tests**

Add a fake harness that records `capture_artifact` calls and returns `HarnessArtifactRef` values. Add a test where an `ExecutableStep` has `EvidencePolicy(capture_before=True, capture_after=True, artifact_kinds=["screenshot", "ui_tree"])`. Assert prepare and finalize phase reports contain refs and runner events contain `artifact_captured`.

- [x] **Step 2: Run target test to verify RED**

Run: `pytest tests/test_step_runner.py::test_step_runner_captures_before_and_after_artifacts_from_policy -q`

Expected: FAIL because `StepRunner` does not call `capture_artifact` yet.

- [x] **Step 3: Implement minimal capture logic**

In `_runner.py`, add a helper that iterates `step.evidence_policy.artifact_kinds`, calls `harness.capture_artifact(kind, reason, context, step.step_id, phase)`, emits `artifact_captured`, and returns artifact refs for the phase report.

- [x] **Step 4: Run target test to verify GREEN**

Run: `pytest tests/test_step_runner.py::test_step_runner_captures_before_and_after_artifacts_from_policy -q`

Expected: PASS.

### Task 2: Failure Capture And Artifact Errors

**Files:**
- Modify: `tests/test_step_runner.py`
- Modify: `fsq_agent/core/runner/_runner.py`

- [x] **Step 1: Write failing tests**

Add one test where invoke returns failed and `capture_on_failure=True`; assert failure artifacts attach to finalize and `artifact_captured` is emitted. Add one test where `capture_artifact` raises; assert runner still returns a structured result with finalize phase `status="failed"`, `failure_category="artifact_error"`, and a useful error message.

- [x] **Step 2: Run target tests to verify RED**

Run: `pytest tests/test_step_runner.py -q`

Expected: FAIL until failure capture and artifact error handling are implemented.

- [x] **Step 3: Implement failure capture and artifact error handling**

Capture failure artifacts during finalize when the invoke result failed or raised. If capture raises, append a failed finalize report with artifact error details instead of crashing the runner.

- [x] **Step 4: Run target tests to verify GREEN**

Run: `pytest tests/test_step_runner.py -q`

Expected: PASS.

### Task 3: Verification

**Files:**
- No code changes unless verification exposes a regression.

- [x] **Step 1: Run focused core tests**

Run: `pytest tests/test_step_runner.py tests/test_step_sequence_runner.py tests/test_evidence_recorder.py tests/test_android_harness.py -q`

Expected: PASS.

- [x] **Step 2: Run full test suite and diff check**

Run: `pytest -q && git diff --check`

Expected: PASS.

## Self-Review

- Spec coverage: Covers before, after, failure artifact capture, event emission, phase report refs, and artifact capture errors.
- Placeholder scan: No placeholders remain.
- Type consistency: Uses existing `HarnessArtifactRef` from harness capture and `EvidenceArtifactRef` in phase reports through model-compatible conversion if needed.
