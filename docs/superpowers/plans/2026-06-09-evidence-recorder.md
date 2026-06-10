# Evidence Recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first `EvidenceRecorder` implementation that consumes runner events/results, builds an `EvidenceBundle`, and writes an evidence manifest JSON file.

**Architecture:** `EvidenceRecorder` lives in `fsq_agent/core/evidence/_recorder.py`, depends only on `fsq_agent.models`, and remains separate from `StepRunner`, harness execution, report generation, verifier logic, and binary artifact copying. It records historical facts only.

**Tech Stack:** Python, Pydantic `model_dump(mode="json")`, pathlib, json, pytest.

---

## File Structure

- Modify `fsq_agent/core/SPEC.md`: document `EvidenceRecorder` public API and boundary.
- Create `fsq_agent/core/evidence/_recorder.py`: implement in-memory recording, bundle construction, and manifest writing.
- Modify `fsq_agent/core/evidence/__init__.py`: export `EvidenceRecorder`.
- Modify `fsq_agent/core/__init__.py`: export `EvidenceRecorder`.
- Create `tests/test_evidence_recorder.py`: tests for bundle construction and manifest writing.

### Task 1: In-Memory Evidence Bundle

**Files:**
- Create: `tests/test_evidence_recorder.py`
- Create: `fsq_agent/core/evidence/_recorder.py`
- Modify: `fsq_agent/core/evidence/__init__.py`
- Modify: `fsq_agent/core/__init__.py`

- [x] **Step 1: Write failing in-memory recorder test**

Create a test that imports `EvidenceRecorder`, records two `RunnerEvent` values and one `RunnerStepResult`, calls `build_bundle()`, and asserts the bundle contains the run id, events, steps, artifact refs from phase reports, and metadata.

- [x] **Step 2: Run in-memory recorder test to verify it fails**

Run: `pytest tests/test_evidence_recorder.py::test_evidence_recorder_builds_bundle_from_events_and_step_results -q`

Expected: FAIL because `EvidenceRecorder` is not implemented/exported.

- [x] **Step 3: Implement minimal in-memory recorder**

Implement `EvidenceRecorder.__init__(run_id, output_dir, bundle_id=None, metadata=None)`, `record_event`, `record_step_result`, and `build_bundle`. `build_bundle` should collect artifact refs from every phase report and return an `EvidenceBundle`.

- [x] **Step 4: Run in-memory recorder test to verify it passes**

Run: `pytest tests/test_evidence_recorder.py::test_evidence_recorder_builds_bundle_from_events_and_step_results -q`

Expected: PASS.

### Task 2: Manifest Writing

**Files:**
- Modify: `tests/test_evidence_recorder.py`
- Modify: `fsq_agent/core/evidence/_recorder.py`

- [x] **Step 1: Write failing manifest writer test**

Add a test that records one event and one failed step result, calls `write_manifest()`, reads `evidence-manifest.json`, and asserts JSON contains `bundle_id`, `run_id`, step failure category, phase reports, and artifact path strings.

- [x] **Step 2: Run manifest writer test to verify it fails**

Run: `pytest tests/test_evidence_recorder.py::test_evidence_recorder_writes_manifest_json -q`

Expected: FAIL until `write_manifest` is implemented.

- [x] **Step 3: Implement manifest writing**

Implement `write_manifest(filename="evidence-manifest.json") -> Path`. It should create `output_dir`, build the bundle, set `manifest_path`, serialize with `model_dump(mode="json")`, and write indented UTF-8 JSON.

- [x] **Step 4: Run manifest writer test to verify it passes**

Run: `pytest tests/test_evidence_recorder.py::test_evidence_recorder_writes_manifest_json -q`

Expected: PASS.

### Task 3: Verification And Commit

**Files:**
- Verify: touched code, tests, and spec

- [x] **Step 1: Run evidence, runner, and contract tests**

Run: `pytest tests/test_evidence_recorder.py tests/test_step_runner.py tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 2: Run full test suite**

Run: `pytest -q`

Expected: PASS.

- [x] **Step 3: Run lint and whitespace checks**

Run: `python3 -m ruff check fsq_agent/core tests/test_evidence_recorder.py` and `git diff --check`.

Expected: both pass.

- [ ] **Step 4: Commit implementation**

Run: `git add fsq_agent/core/SPEC.md fsq_agent/core/__init__.py fsq_agent/core/evidence/__init__.py fsq_agent/core/evidence/_recorder.py tests/test_evidence_recorder.py docs/superpowers/plans/2026-06-09-evidence-recorder.md && git commit -m "feat: add evidence recorder"`
