# FSQ Evidence Manifest Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify the deterministic FSQ execution path can produce an evidence manifest JSON with events, step results, source refs, and artifact refs.

**Architecture:** Keep `StepSequenceRunner` free of manifest-writing side effects. The integration flow composes `FsqCaseLoader`, `FsqExecutableStepAdapter`, `StepSequenceRunner`, `EvidenceRecorder`, and explicit `EvidenceRecorder.write_manifest()` from test/caller code.

**Tech Stack:** Python 3, pytest, Pydantic model JSON serialization.

---

### Task 1: End-To-End Manifest Smoke Test

**Files:**
- Create: `tests/test_fsq_evidence_manifest_smoke.py`
- Modify: `fsq_agent/core/SPEC.md`

- [x] **Step 1: Write the integration test**

Create a fake harness that returns passed action results and fake screenshot/UI-tree artifact refs. Load an inline `.codex.yaml`, convert it with `FsqExecutableStepAdapter`, assign an evidence policy to one step, run `StepSequenceRunner`, then call `EvidenceRecorder.write_manifest()` explicitly.

- [x] **Step 2: Verify RED or immediate GREEN**

Run: `pytest tests/test_fsq_evidence_manifest_smoke.py -q`

Expected: PASS if existing components already compose correctly. If it fails, fix only the integration bug exposed by the test.

- [x] **Step 3: Assert manifest shape**

The test must assert the manifest JSON includes `run_id`, step ids, FSQ source refs, `artifact_captured` events, and artifact paths under `bundle.artifacts`.

### Task 2: Verification

**Files:**
- No code changes unless the smoke test exposes a real integration bug.

- [x] **Step 1: Run focused tests**

Run: `pytest tests/test_fsq_evidence_manifest_smoke.py tests/test_fsq_executable_step_adapter.py tests/test_step_sequence_runner.py tests/test_evidence_recorder.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run: `pytest -q && git diff --check`

Expected: PASS.

## Self-Review

- Spec coverage: Confirms explicit manifest writing after sequence execution without adding side effects to `StepSequenceRunner`.
- Placeholder scan: No placeholders remain.
- Type consistency: Uses existing public APIs only.
