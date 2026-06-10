# Step Runner Minimal Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the minimal synchronous `StepRunner` slice that runs one `ExecutableStep` through `prepare`, `invoke`, and `finalize` with a test fake harness.

**Architecture:** `StepRunner` lives in `fsq_agent/core/runner/_runner.py`, consumes model-owned contracts from `fsq_agent.models`, and depends only on `HarnessInterface`. Fake harnesses stay in tests. The runner emits `RunnerEvent` values in memory and returns a `RunnerStepResult`; it does not write evidence manifests, run real platforms, or integrate CLI/report/verifier.

**Tech Stack:** Python, Pydantic contracts, `typing.Protocol`, pytest.

---

## File Structure

- Modify `fsq_agent/core/SPEC.md`: document the minimal synchronous `StepRunner` API.
- Create `fsq_agent/core/runner/_runner.py`: implement `StepRunner` with `run_step(run_id, step)` and `events`.
- Modify `fsq_agent/core/runner/__init__.py`: export `StepRunner`.
- Modify `fsq_agent/core/__init__.py`: export `StepRunner`.
- Create `tests/test_step_runner.py`: tests with in-test fake harnesses for success and failure paths.

### Task 1: Successful Step Protocol

**Files:**
- Create: `tests/test_step_runner.py`
- Create: `fsq_agent/core/runner/_runner.py`
- Modify: `fsq_agent/core/runner/__init__.py`
- Modify: `fsq_agent/core/__init__.py`

- [x] **Step 1: Write failing success-path test**

Create a test that imports `StepRunner`, runs one action step through an in-test fake harness, asserts `prepare`, `invoke`, and `finalize` phase reports, asserts runner events, and asserts harness call order.

- [x] **Step 2: Run success-path test to verify it fails**

Run: `pytest tests/test_step_runner.py::test_step_runner_runs_successful_step_through_three_phases -q`

Expected: FAIL because `StepRunner` is not implemented/exported.

- [x] **Step 3: Implement minimal success-path runner**

Implement `StepRunner.__init__`, `events`, `_emit`, and `run_step`. The success path should call `get_context`, `before_action`, `invoke_action`, and `after_action`, emit events, create three `StepPhaseReport` values, and return `RunnerStepResult(status="passed")`.

- [x] **Step 4: Run success-path test to verify it passes**

Run: `pytest tests/test_step_runner.py::test_step_runner_runs_successful_step_through_three_phases -q`

Expected: PASS.

### Task 2: Invoke Failure Protocol

**Files:**
- Modify: `tests/test_step_runner.py`
- Modify: `fsq_agent/core/runner/_runner.py`

- [x] **Step 1: Write failing invoke-failure test**

Add a fake harness whose `invoke_action` raises `RuntimeError`. Assert the result has `status="failed"`, an invoke phase report with `failure_category="action_error"`, a finalize phase report still exists, `after_action` was called with no action result, and `step_error` / `step_finish` events were emitted.

- [x] **Step 2: Run invoke-failure test to verify it fails**

Run: `pytest tests/test_step_runner.py::test_step_runner_wraps_invoke_exception_and_still_finalizes -q`

Expected: FAIL until exception handling and failure finalization are implemented.

- [x] **Step 3: Implement invoke failure handling**

Catch invoke exceptions, classify through `harness.classify_error(error, "invoke", step)`, record failed `StepPhaseReport`, emit `step_error`, call `after_action(step, context, None)`, record finalize report, and return failed `RunnerStepResult` instead of raising.

- [x] **Step 4: Run invoke-failure test to verify it passes**

Run: `pytest tests/test_step_runner.py::test_step_runner_wraps_invoke_exception_and_still_finalizes -q`

Expected: PASS.

### Task 3: Verification And Commit

**Files:**
- Verify: touched code, tests, and spec

- [x] **Step 1: Run runner and contract tests**

Run: `pytest tests/test_step_runner.py tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 2: Run model tests**

Run: `pytest tests/test_models.py -q`

Expected: PASS.

- [x] **Step 3: Run full test suite**

Run: `pytest -q`

Expected: PASS.

- [x] **Step 4: Run lint and whitespace checks**

Run: `python3 -m ruff check fsq_agent/core tests/test_step_runner.py` and `git diff --check`.

Expected: both pass.

- [ ] **Step 5: Commit implementation**

Run: `git add fsq_agent/core/SPEC.md fsq_agent/core/__init__.py fsq_agent/core/runner/__init__.py fsq_agent/core/runner/_runner.py tests/test_step_runner.py docs/superpowers/plans/2026-06-09-step-runner-minimal-slice.md && git commit -m "feat: add minimal step runner"`
