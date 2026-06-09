# FSQ Executable Step Sequence Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert loaded FSQ cases into ordered `ExecutableStep` records and execute those records through a platform-neutral sequence runner that records evidence facts.

**Architecture:** The `fsq` module will add `FsqExecutableStepAdapter`, which depends only on shared models and converts `FsqCase.commands` into `list[ExecutableStep]`. The `core` module will add `StepSequenceRunner`, which depends only on shared models, `StepRunner`, and `EvidenceRecorder`; it will not import or parse FSQ YAML.

**Tech Stack:** Python 3, Pydantic shared models, pytest.

---

### Task 1: FSQ Executable Step Adapter

**Files:**
- Create: `fsq_agent/fsq/_step_adapter.py`
- Modify: `fsq_agent/fsq/__init__.py`
- Test: `tests/test_fsq_executable_step_adapter.py`

- [x] **Step 1: Write failing adapter tests**

Add tests covering a loaded Android FSQ-style case, string shorthand normalization, list payload normalization, setup/teardown/assertion kind mapping, source refs, timeout copy, and malformed command errors.

- [x] **Step 2: Run adapter tests to verify RED**

Run: `pytest tests/test_fsq_executable_step_adapter.py -q`

Expected: FAIL because `FsqExecutableStepAdapter` is not implemented/exported.

- [x] **Step 3: Implement minimal adapter**

Create `_step_adapter.py` with `FsqExecutableStepAdapter.to_executable_steps(case: FsqCase) -> list[ExecutableStep]`. Preserve FSQ action names, normalize params according to `fsq_agent/fsq/SPEC.md`, and raise `ConfigurationError` for malformed commands.

- [x] **Step 4: Export adapter**

Update `fsq_agent/fsq/__init__.py` to export `FsqExecutableStepAdapter` through explicit `__all__`.

- [x] **Step 5: Run adapter tests to verify GREEN**

Run: `pytest tests/test_fsq_executable_step_adapter.py -q`

Expected: PASS.

### Task 2: Core Step Sequence Runner

**Files:**
- Create: `fsq_agent/core/runner/_sequence.py`
- Modify: `fsq_agent/core/runner/__init__.py`
- Modify: `fsq_agent/core/__init__.py`
- Test: `tests/test_step_sequence_runner.py`

- [x] **Step 1: Write failing sequence runner tests**

Add tests proving `StepSequenceRunner` runs steps in order, records `StepRunner` events and step results into `EvidenceRecorder`, returns an `EvidenceBundle`, and stops after the first failed step.

- [x] **Step 2: Run sequence tests to verify RED**

Run: `pytest tests/test_step_sequence_runner.py -q`

Expected: FAIL because `StepSequenceRunner` is not implemented/exported.

- [x] **Step 3: Implement minimal sequence runner**

Create `_sequence.py` with `StepSequenceRunner(harness, evidence_recorder)` and `run_steps(run_id: str, steps: Sequence[ExecutableStep]) -> EvidenceBundle`. For each step, create a `StepRunner`, run the step, record its events and result, and stop on `failed`, `cancelled`, or `skipped`.

- [x] **Step 4: Export sequence runner**

Update `fsq_agent/core/runner/__init__.py` and `fsq_agent/core/__init__.py` to export `StepSequenceRunner` through explicit `__all__`.

- [x] **Step 5: Run sequence tests to verify GREEN**

Run: `pytest tests/test_step_sequence_runner.py -q`

Expected: PASS.

### Task 3: Integration And Verification

**Files:**
- Test: `tests/test_fsq_executable_step_adapter.py`
- Test: `tests/test_step_sequence_runner.py`
- Existing tests may be updated only if public exports require it.

- [x] **Step 1: Run focused Batch 5 tests**

Run: `pytest tests/test_fsq_executable_step_adapter.py tests/test_step_sequence_runner.py -q`

Expected: PASS.

- [x] **Step 2: Run adjacent regression tests**

Run: `pytest tests/test_fsq.py tests/test_step_runner.py tests/test_evidence_recorder.py tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 3: Run full suite and diff check**

Run: `pytest -q && git diff --check`

Expected: PASS.

## Self-Review

- Spec coverage: The plan implements the newly approved `FsqExecutableStepAdapter` and `StepSequenceRunner` interfaces only.
- Placeholder scan: No placeholders remain.
- Type consistency: `fsq` produces `ExecutableStep` models only; `core` consumes `ExecutableStep` and does not import `fsq`.
