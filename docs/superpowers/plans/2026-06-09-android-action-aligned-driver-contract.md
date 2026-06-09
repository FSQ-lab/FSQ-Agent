# Android Action-Aligned Driver Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the Android harness and driver protocol with the FSQ AI Test DSL action names used by the Android testcase corpus.

**Architecture:** `AndroidHarness` remains the runner-facing `HarnessInterface` implementation and dispatches `ExecutableStep.action_name` values. `AndroidDriverInterface` exposes Python snake_case methods that map one-to-one to phase-1 FSQ actions, while `AndroidHarness` normalizes bare/string/list command params before calling the driver.

**Tech Stack:** Python 3, Protocol interfaces, Pydantic shared models, pytest.

---

### Task 1: Update Android Harness Tests First

**Files:**
- Modify: `tests/test_android_harness.py`

- [x] **Step 1: Replace fake driver methods with action-aligned methods**

Update `FakeAndroidDriver` so it exposes `launch_app`, `kill_app`, `tap_on`, `long_press_on`, `input_text`, `press_key`, `swipe`, `perform_actions`, `assert_visible`, `assert_not_visible`, `assert_state`, and `assert_with_ai`. Each method appends `(method_name, params)` to `self.calls` and returns a small dict identifying the action.

- [x] **Step 2: Add focused dispatch tests**

Add tests that prove these FSQ action names dispatch to the expected driver methods:

```python
def test_android_harness_dispatches_fsq_action_names_to_driver() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)
    context = harness.get_context()

    cases = [
        ("launchApp", {}, "launch_app"),
        ("killApp", {}, "kill_app"),
        ("tapOn", {"target": "Menu"}, "tap_on"),
        ("assertVisible", {"target": "Menu"}, "assert_visible"),
        ("inputText", {"text": "bing.com"}, "input_text"),
        ("longPressOn", {"target": "Address bar"}, "long_press_on"),
        ("swipe", {"direction": "up", "duration": 1000}, "swipe"),
        ("assertNotVisible", {"target": "Dialog"}, "assert_not_visible"),
        ("assert", {"text": {"contains": "bing.com"}}, "assert_state"),
        ("assertWithAI", {"prompt": "Verify Bing"}, "assert_with_ai"),
    ]

    for action_name, params, _method_name in cases:
        result = harness.invoke_action(_step(action_name, params), context)
        assert result.status == "passed"
        assert result.action_name == action_name

    assert driver.calls == [("context", None)] + [
        (method_name, params) for _action_name, params, method_name in cases
    ]
```

- [x] **Step 3: Add parameter normalization tests**

Add one test for `pressKey` string shorthand and one test for `performActions` list wrapping:

```python
def test_android_harness_normalizes_press_key_string_shorthand() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)

    result = harness.invoke_action(_step("pressKey", {"value": "Back"}), harness.get_context())

    assert result.status == "passed"
    assert driver.calls[-1] == ("press_key", {"key": "Back"})


def test_android_harness_wraps_perform_actions_list() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)
    actions = [{"type": "none", "id": "wait", "actions": [{"type": "pause", "duration": 1}]}]

    result = harness.invoke_action(_step("performActions", {"value": actions}), harness.get_context())

    assert result.status == "passed"
    assert driver.calls[-1] == ("perform_actions", {"actions": actions})
```

- [x] **Step 4: Run targeted tests and verify RED**

Run: `pytest tests/test_android_harness.py -q`

Expected: FAIL because `AndroidHarness` still dispatches `tap`, `inputText`, and `back`, and `AndroidDriverInterface` does not yet define phase-1 methods.

### Task 2: Implement Action-Aligned Protocol And Dispatch

**Files:**
- Modify: `fsq_agent/core/harness/_android_driver.py`
- Modify: `fsq_agent/core/harness/_android.py`

- [x] **Step 1: Update `AndroidDriverInterface` method signatures**

Replace the existing `tap` and `back` protocol methods with the phase-1 action-aligned methods from `fsq_agent/core/SPEC.md`.

- [x] **Step 2: Update `AndroidHarness.action_space`**

Return entries for the 12 phase-1 FSQ action names: `launchApp`, `killApp`, `tapOn`, `assertVisible`, `performActions`, `assert`, `pressKey`, `inputText`, `assertNotVisible`, `longPressOn`, `swipe`, and `assertWithAI`.

- [x] **Step 3: Update `AndroidHarness.invoke_action` dispatch**

Use a small dispatch map from FSQ action name to driver method name. Normalize params before dispatch:

```python
if step.action_name in {"launchApp", "killApp"}:
    params = {}
elif step.action_name == "pressKey" and "value" in step.params:
    params = {"key": step.params["value"]}
elif step.action_name == "performActions" and "value" in step.params:
    params = {"actions": step.params["value"]}
else:
    params = step.params
```

Then call the mapped driver method and wrap the returned output in `HarnessActionResult(status="passed", action_name=step.action_name, output=output)`.

- [x] **Step 4: Preserve unsupported action behavior**

Keep unsupported action behavior as a failed `HarnessActionResult` with `failure_category="configuration_error"` and `error_message=f"Unsupported Android action: {step.action_name}"`.

- [x] **Step 5: Run targeted tests and verify GREEN**

Run: `pytest tests/test_android_harness.py -q`

Expected: PASS.

### Task 3: Verify Core Suite

**Files:**
- No code changes unless verification reveals a real regression.

- [x] **Step 1: Run focused core tests**

Run: `pytest tests/test_android_harness.py tests/test_step_runner.py tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 2: Run full test suite**

Run: `pytest -q`

Expected: PASS.

- [x] **Step 3: Review final diff**

Run: `git diff -- fsq_agent/core/SPEC.md fsq_agent/core/harness/_android.py fsq_agent/core/harness/_android_driver.py tests/test_android_harness.py docs/superpowers/plans/2026-06-09-android-action-aligned-driver-contract.md`

Expected: Diff only contains the approved spec, plan, Android harness/protocol updates, and Android harness tests.

## Self-Review

- Spec coverage: The plan covers the complete command list in spec documentation and implements only the approved phase-1 Android action methods.
- Placeholder scan: No placeholders remain.
- Type consistency: FSQ action names stay camelCase in `ExecutableStep.action_name`; driver methods use the snake_case names listed in `fsq_agent/core/SPEC.md`.
