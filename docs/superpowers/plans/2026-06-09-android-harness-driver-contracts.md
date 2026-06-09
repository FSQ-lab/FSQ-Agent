# Android Harness Driver Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend-free Android harness contracts: built-in `AndroidHarness` implementing `HarnessInterface`, and `AndroidDriverInterface` as the lower-level user extension point.

**Architecture:** `AndroidHarness` lives in `fsq_agent/core/harness/_android.py` and depends on `AndroidDriverInterface`, shared models, and optional `ArtifactStore`. `AndroidDriverInterface` lives in `fsq_agent/core/harness/_android_driver.py` and exposes only primitive Android operations. Tests use fake drivers; no Appium, uiautomator2, MCP, or real device integration is included.

**Tech Stack:** Python, `typing.Protocol`, Pydantic model contracts, pytest.

---

## File Structure

- Modify `fsq_agent/core/SPEC.md`: document Android driver/harness API.
- Create `fsq_agent/core/harness/_android_driver.py`: define `AndroidDriverInterface` protocol.
- Create `fsq_agent/core/harness/_android.py`: implement `AndroidHarness` action dispatch and artifact capture.
- Modify `fsq_agent/core/harness/__init__.py`: export Android harness symbols.
- Modify `fsq_agent/core/__init__.py`: export Android harness symbols.
- Create `tests/test_android_harness.py`: fake-driver tests for dispatch, artifact capture, and unsupported actions.

### Task 1: Android Driver Protocol And Tap Dispatch

**Files:**
- Create: `tests/test_android_harness.py`
- Create: `fsq_agent/core/harness/_android_driver.py`
- Create: `fsq_agent/core/harness/_android.py`
- Modify: `fsq_agent/core/harness/__init__.py`
- Modify: `fsq_agent/core/__init__.py`

- [x] **Step 1: Write failing tap dispatch test**

Create a fake Android driver with `context`, `tap`, `input_text`, `back`, `screenshot`, and `ui_tree` methods. Assert `AndroidHarness` satisfies `HarnessInterface`, returns Android context from the driver, dispatches `ExecutableStep(action_name="tap")` to `driver.tap(params)`, and returns `HarnessActionResult(status="passed")`.

- [x] **Step 2: Run tap dispatch test to verify it fails**

Run: `pytest tests/test_android_harness.py::test_android_harness_dispatches_tap_to_driver -q`

Expected: FAIL because `AndroidHarness` and `AndroidDriverInterface` are not implemented/exported.

- [x] **Step 3: Implement driver protocol and tap dispatch**

Implement `AndroidDriverInterface` as a runtime-checkable protocol. Implement `AndroidHarness.__init__`, `get_context`, `action_space`, no-op `before_action`/`after_action`, and `invoke_action` support for `tap`.

- [x] **Step 4: Run tap dispatch test to verify it passes**

Run: `pytest tests/test_android_harness.py::test_android_harness_dispatches_tap_to_driver -q`

Expected: PASS.

### Task 2: Input, Back, Unsupported Action, And Artifact Capture

**Files:**
- Modify: `tests/test_android_harness.py`
- Modify: `fsq_agent/core/harness/_android.py`

- [x] **Step 1: Write failing dispatch and artifact tests**

Add tests for `inputText`, `back`, unsupported action handling, screenshot artifact capture, and UI-tree artifact capture with `ArtifactStore`.

- [x] **Step 2: Run Android harness tests to verify they fail**

Run: `pytest tests/test_android_harness.py -q`

Expected: FAIL until input/back/unsupported/capture behavior is implemented.

- [x] **Step 3: Implement remaining AndroidHarness contract behavior**

Implement dispatch for `inputText` and `back`; unsupported actions return failed `HarnessActionResult(failure_category="configuration_error")`; `capture_artifact("screenshot", ...)` writes screenshot bytes through `ArtifactStore`; `capture_artifact("ui_tree", ...)` writes UI tree JSON through `ArtifactStore`; no store raises a clear `RuntimeError` for artifact capture.

- [x] **Step 4: Run Android harness tests to verify they pass**

Run: `pytest tests/test_android_harness.py -q`

Expected: PASS.

### Task 3: Verification And Commit

**Files:**
- Verify: touched code, tests, and spec

- [x] **Step 1: Run Android/core tests**

Run: `pytest tests/test_android_harness.py tests/test_step_runner.py tests/test_artifact_store.py tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 2: Run full test suite**

Run: `pytest -q`

Expected: PASS.

- [x] **Step 3: Run lint and whitespace checks**

Run: `python3 -m ruff check fsq_agent/core tests/test_android_harness.py` and `git diff --check`.

Expected: both pass.

- [ ] **Step 4: Commit implementation**

Run: `git add fsq_agent/core/SPEC.md fsq_agent/core/__init__.py fsq_agent/core/harness/__init__.py fsq_agent/core/harness/_android.py fsq_agent/core/harness/_android_driver.py tests/test_android_harness.py docs/superpowers/plans/2026-06-09-android-harness-driver-contracts.md && git commit -m "feat: add android harness driver contracts"`
