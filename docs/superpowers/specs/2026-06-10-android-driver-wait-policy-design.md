# Android Driver Wait Policy Design

## Context

Strict core execution successfully runs Android cases through the new `run-strict-core` CLI, but one real-device case exposed a timing issue: after tapping `New InPrivate Tab`, the immediate `assertVisible` for `Browse InPrivate` failed with `target_resolution_error`, while a later UI dump showed the element present.

This is a deterministic execution stability issue, not a recovery or self-healing feature. The strict path should still fail when an authored locator cannot resolve, but it should allow normal Android UI transitions enough time to settle before declaring the target missing.

## Decision

Element wait policy belongs in the Android device execution layer, not in the YAML testcase schema.

FSQ YAML should continue to describe user actions and assertions only. It must not require authors or future AI testcase generators to reason about per-step wait durations. The short-term implementation will use a fixed Android driver default wait for element resolution.

Default values for the first implementation:

- Element wait timeout: `10.0` seconds.
- Polling behavior: delegated to `uiautomator2` built-in selector wait APIs when available.
- YAML timeout fields: not read and not added by this change.
- CLI/config timeout options: not added by this change.

## Scope

The short-term change applies only to `UiAutomator2AndroidDriver` element resolution.

The driver methods that require a target element should wait before reporting `target_resolution_error`:

- `tap_on`
- `long_press_on`
- `input_text`
- `assert_visible`
- `assert_state`

`assert_not_visible` needs inverse behavior:

- If the target is already absent, pass immediately.
- If the target is present, wait up to the default timeout for it to disappear.
- If the target remains visible after the timeout, fail with `assertion_error`.

This change does not alter `AndroidDriverInterface`, `AndroidHarness`, `StepRunner`, evidence bundle schemas, or report generation.

## Implementation Shape

`UiAutomator2AndroidDriver` should expose private helpers only:

```python
DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS = 10.0


def _wait_for_exists(self, selector: object) -> bool:
    wait = getattr(selector, "wait", None)
    if callable(wait):
        try:
            return bool(wait(exists=True, timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))
        except TypeError:
            return bool(wait(timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))
    return self._exists(selector)


def _wait_for_not_exists(self, selector: object) -> bool:
    wait_gone = getattr(selector, "wait_gone", None)
    if callable(wait_gone):
        return bool(wait_gone(timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))

    wait = getattr(selector, "wait", None)
    if callable(wait):
        try:
            return bool(wait(exists=False, timeout=DEFAULT_ELEMENT_WAIT_TIMEOUT_SECONDS))
        except TypeError:
            pass

    return not self._exists(selector)
```

The helper first uses uiautomator2's built-in `UiObject.wait(exists=True, timeout=...)` and `UiObject.wait_gone(timeout=...)`. XPath selectors expose a different `wait(timeout=...)` shape, so `_wait_for_exists` should catch `TypeError` and retry without `exists=True`.

The fallback to `_exists` is for fake test selectors or future selector objects that do not expose wait APIs. The production uiautomator2 path should use the backend wait API.

## Strictness Boundary

This is not locator fallback and not AI-assisted recovery. The driver waits for the same authored selector. If that selector cannot resolve within the default wait, the result remains a strict `target_resolution_error`.

The run report should continue to represent strict truth: passed only when the authored action/assertion succeeds without fallback or mutation.

## Future Direction

If real-device runs show that one fixed timeout is insufficient, the next step should be an FSQ-owned Android wait policy, for example:

```text
AndroidHarness
  -> AndroidWaitPolicy
      element_timeout_seconds
      animation_timeout_seconds
      app_launch_timeout_seconds
      poll_interval_seconds
```

That policy can later differ by execution mode, such as strict regression versus recovery runs. The first implementation intentionally avoids configuration surface area until the actual stability data justifies it.

## Acceptance Criteria

- Existing FSQ YAML files run without adding timeout fields.
- `tap_on`, `long_press_on`, `input_text`, `assert_visible`, and `assert_state` wait for targets before failing target resolution.
- `assert_not_visible` waits for visible targets to disappear and passes immediately when already absent.
- Unit tests prove the driver calls uiautomator2-style wait APIs.
- A real `run-strict-core` retry of the InPrivate case should advance past the previously failing `Browse InPrivate` assertion if the element appears within 10 seconds.
