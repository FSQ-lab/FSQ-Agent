# UiAutomator2 Android Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal optional `UiAutomator2AndroidDriver` backend that satisfies `AndroidDriverInterface` without requiring a real Android device in tests.

**Architecture:** `StepRunner` and `EvidenceRecorder` stay platform-neutral. `AndroidHarness` continues to own runner-facing action dispatch and result conversion, while `UiAutomator2AndroidDriver` owns only uiautomator2 mechanics behind the existing `AndroidDriverInterface`. Unit tests inject fake device objects so the driver can be verified without installing or launching uiautomator2.

**Tech Stack:** Python, pytest, optional `uiautomator2` package via `fsq-agent[android]`, existing `AndroidHarness`, `AndroidDriverInterface`, and `ConfigurationError`.

---

### File Structure

- Modify: `fsq_agent/core/SPEC.md` to define the uiautomator2 backend contract.
- Modify: `pyproject.toml` to add optional dependency extra `android = ["uiautomator2>=3.0.0"]`.
- Modify: `fsq_agent/core/harness/__init__.py` to export `UiAutomator2AndroidDriver`.
- Modify: `fsq_agent/core/__init__.py` to export `UiAutomator2AndroidDriver` from the top-level core public API.
- Create: `fsq_agent/core/harness/_uiautomator2_driver.py` for the backend implementation.
- Create: `tests/test_uiautomator2_android_driver.py` for fake-device tests.

### Task 1: Document And Dependency Boundary

**Files:**
- Modify: `fsq_agent/core/SPEC.md`
- Modify: `pyproject.toml`

- [x] **Step 1: Update core SPEC**

Document `UiAutomator2AndroidDriver`, fake-device injection, lazy dependency import, locator mapping, failure result shape, and the decision that AI assertion remains unimplemented in this backend slice.

- [x] **Step 2: Add optional android extra**

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
android = [
    "uiautomator2>=3.0.0",
]
```

### Task 2: Write Failing Driver Tests

**Files:**
- Create: `tests/test_uiautomator2_android_driver.py`

- [x] **Step 1: Add fake device tests**

Cover these behaviors:

```python
def test_uiautomator2_driver_context_launch_kill_and_artifacts() -> None:
    device = FakeDevice()
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    assert driver.context()["session_id"] == "uiautomator2:fake-device"
    assert driver.launch_app({})["status"] == "passed"
    assert driver.kill_app({})["status"] == "passed"
    assert driver.screenshot() == b"fake-png"
    assert driver.ui_tree() == {"xml": "<hierarchy />"}


def test_uiautomator2_driver_actions_use_locator_selectors() -> None:
    device = FakeDevice()
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    assert driver.tap_on({"locator": {"resourceId": "login"}})["status"] == "passed"
    assert driver.input_text({"text": "hello", "locator": {"text": "Search"}})["status"] == "passed"
    assert driver.press_key({"key": "Back"})["status"] == "passed"
    assert driver.swipe({"direction": "up", "duration": 100})["status"] == "passed"


def test_uiautomator2_driver_assertion_and_missing_target_results() -> None:
    device = FakeDevice(exists=False)
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    result = driver.assert_visible({"locator": {"text": "Missing"}})

    assert result["status"] == "failed"
    assert result["failure_category"] == "target_resolution_error"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_uiautomator2_android_driver.py -q`

Expected: FAIL with import error for `UiAutomator2AndroidDriver`.

### Task 3: Implement Driver And Exports

**Files:**
- Create: `fsq_agent/core/harness/_uiautomator2_driver.py`
- Modify: `fsq_agent/core/harness/__init__.py`
- Modify: `fsq_agent/core/__init__.py`

- [x] **Step 1: Implement lazy device creation**

Implement `__init__(app_id: str, serial: str | None = None, device: object | None = None)`. If `device` is omitted, import `uiautomator2` lazily and connect. On missing import, raise `ConfigurationError("uiautomator2 is required for UiAutomator2AndroidDriver.", context={"install": "pip install fsq-agent[android]"})`.

- [x] **Step 2: Implement context, app lifecycle, and artifacts**

Implement `context`, `launch_app`, `kill_app`, `screenshot`, and `ui_tree` using common uiautomator2 device methods with fake-device-compatible calls.

- [x] **Step 3: Implement action and assertion methods**

Implement locator resolution, `tap_on`, `long_press_on`, `input_text`, `press_key`, `swipe`, `perform_actions`, `assert_visible`, `assert_not_visible`, `assert_state`, and `assert_with_ai` result dictionaries.

- [x] **Step 4: Export the driver**

Add `UiAutomator2AndroidDriver` to `fsq_agent.core.harness.__all__` and `fsq_agent.core.__all__`.

### Task 4: Verify And Commit

**Files:**
- Modified files from Tasks 1-3.

- [x] **Step 1: Run narrow and related tests**

Run: `pytest tests/test_uiautomator2_android_driver.py tests/test_android_harness.py tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run: `pytest -q`

Expected: PASS.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 3: Commit**

Run:

```bash
git add pyproject.toml fsq_agent/core/SPEC.md fsq_agent/core/__init__.py fsq_agent/core/harness/__init__.py fsq_agent/core/harness/_uiautomator2_driver.py tests/test_uiautomator2_android_driver.py docs/superpowers/plans/2026-06-09-uiautomator2-android-driver.md
git commit -m "feat: add uiautomator2 android driver"
```

### Self-Review

- Spec coverage: The plan covers optional dependency, lazy import, fake-device injection, locator mapping, backend result shape, exports, and tests.
- Placeholder scan: No `TBD`, `TODO`, or unspecified code steps remain.
- Type consistency: The driver implements the existing `AndroidDriverInterface` method names and returns dictionaries consumed by `AndroidHarness`.
