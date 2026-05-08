# Module: observation

## Purpose

Capture and persist execution evidence after each step, including screenshots, UI element trees, structured logs, and trace events.

## Dependencies

- `models`: Uses `ExecutionStep`, `StepResult`, `ObservationSettings`, and `ObservationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ScreenCapture`: Captures screenshots to configured storage and returns evidence paths.
- `UITreeExtractor`: Extracts accessibility or window control trees for the current application state.
- `ExecutionLogger`: Writes structured step logs and run-level trace events.
- `ObservationRecorder`: Coordinates screenshot, UI tree, timing, and log capture for each execution step.

## Internal Structure

- `__init__.py`: Public exports only.
- `_screenshot.py`: Screenshot capture using platform-specific backends such as `mss` or `pyautogui`.
- `_ui_tree.py`: UI tree extraction using platform accessibility APIs such as `pywinauto` on Windows.
- `_logger.py`: Structured logging setup and event writing.
- `_recorder.py`: Evidence coordination after step execution.
- `SPEC.md`: Module design.

## Error Handling

Observation failures that do not invalidate task execution should be recorded as degraded evidence when possible. Unexpected capture failures raise `ObservationError` from `models` with context about the backend and target artifact.

## Design Decisions

- Evidence capture is separate from tool execution so failures can be diagnosed independently.
- The initial target platform is Windows, but backend boundaries allow future macOS and Linux support.
- Each step should have a stable evidence manifest entry even when screenshot or UI tree capture is disabled.
