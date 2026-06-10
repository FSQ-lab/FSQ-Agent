# Module: core

## Purpose

Define the shared execution-core orchestration layer for FSQ-Agent. The core module owns the StepRunner protocol boundary, harness capability interface, and evidence-recording coordination points that will let FSQ YAML execution and natural-goal execution converge before platform operations.

The module is contract-first. Implementation must not start until this SPEC and the corresponding shared model changes in `fsq_agent/models/SPEC.md` are reviewed and confirmed.

## Dependencies

- `models`: Uses shared execution-core data structures such as executable steps, phase reports, runner events, harness context/results, artifact refs, evidence bundle manifests, and execution failure/status literals.

The core module must not depend on `agent`, `cli`, `fsq`, `report`, `observation`, `knowledge`, `skills`, or concrete platform tool modules in its first contract batch.

## Public Interface

Planned `__init__.py` exports via `__all__`:

- `HarnessInterface`: Protocol describing platform capabilities required by StepRunner. Concrete Android, Web, iOS, and fake harnesses may satisfy the protocol structurally.
- `StepRunner`: Minimal synchronous runner that executes one `ExecutableStep` through the `prepare`, `invoke`, and `finalize` phases using a supplied `HarnessInterface`.
- `StepSequenceRunner`: Minimal synchronous runner that executes an ordered list of `ExecutableStep` records with `StepRunner`, records events and step results, and builds an `EvidenceBundle` through `EvidenceRecorder`.
- `EvidenceRecorder`: Event/result sink that builds an `EvidenceBundle` and writes a JSON manifest for execution facts and artifact references.
- `ArtifactStore`: Evidence artifact path policy and writer for run-local screenshots, UI trees, harness-call JSON, logs, and raw files.
- `UiAutomator2AndroidDriver`: Optional Android backend driver that satisfies `AndroidDriverInterface` using uiautomator2 when the `android` extra is installed.

Planned subpackage exports:

- `fsq_agent.core.runner`: Home for `StepRunner` and runner orchestration helpers. It imports shared runner models from `fsq_agent.models` rather than defining cross-module data models locally.
- `fsq_agent.core.harness`: Home for `HarnessInterface` and future harness-neutral helper code. It imports shared harness models from `fsq_agent.models`.
- `fsq_agent.core.evidence`: Home for `EvidenceRecorder`, `ArtifactStore`, and evidence coordination logic. It imports evidence bundle and artifact models from `fsq_agent.models`.

The first runner implementation exposes a narrow synchronous API:

```python
runner = StepRunner(harness=harness)
result = runner.run_step(run_id="run-1", step=executable_step)
events = runner.events
```

`StepRunner` accepts any object satisfying `HarnessInterface`. Entry-layer code and future factories are responsible for constructing platform-specific harnesses such as Android, Web, iOS, or fake harnesses.

`StepRunner` owns evidence-policy timing. When `ExecutableStep.evidence_policy` requests artifact capture, the runner should call `HarnessInterface.capture_artifact` with FSQ-owned `step_id`, `phase`, and a stable reason string. The first evidence-policy implementation should support:

- `capture_before=True`: capture requested `artifact_kinds` during the `prepare` phase after context is available and before `before_action` completes.
- `capture_after=True`: capture requested `artifact_kinds` during the `finalize` phase after `after_action` completes.
- `capture_on_failure=True`: when invoke returns or raises a failure, capture requested `artifact_kinds` during `finalize` with a failure reason.
- `artifact_kinds`: only `screenshot` and `ui_tree` are required in the first implementation. Unsupported kinds should not crash the runner; they should produce a failed finalize phase report with `failure_category="artifact_error"` and a useful error message.

Captured artifact refs should be attached to the corresponding `StepPhaseReport.artifact_refs`, and every successful capture should emit a `RunnerEvent(event_type="artifact_captured")` with payload fields for `artifact_id`, `kind`, `path`, `reason`, and `phase`. The runner must not decide artifact directories or serialize binary data; `HarnessInterface` and `ArtifactStore` handle raw capture and path policy.

The first sequence runner implementation exposes a narrow synchronous API:

```python
runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder)
result = runner.run_steps(run_id="run-1", steps=executable_steps, teardown_steps=teardown_steps)
```

`StepSequenceRunner` accepts only shared `ExecutableStep` records and must not import `fsq`, parse YAML, construct platform drivers, or generate reports. Its first behavior is intentionally small:

- Run normal steps in list order by delegating each step to `StepRunner.run_step`.
- Record every event emitted by each `StepRunner` into the supplied `EvidenceRecorder`.
- Record every `RunnerStepResult` into the supplied `EvidenceRecorder`.
- Stop normal-step execution on the first step whose result status is `failed`, `cancelled`, or `skipped`.
- Always execute supplied `teardown_steps` after normal execution stops or completes, including after failed, cancelled, skipped, or exception-converted normal steps.
- Build and return the current `EvidenceBundle` after execution stops or all steps pass.
- Leave manifest persistence to the caller by requiring an explicit `EvidenceRecorder.write_manifest()` call after `run_steps` when disk output is desired.

The sequence runner should follow xUnit-style control flow internally: a normal-step failure is converted into an internal sequence failure that exits the normal body, while teardown execution is protected by `finally`-style logic. The internal failure mechanism must not leak out of the runner or replace structured evidence; it only controls execution order. Teardown results are recorded as ordinary `RunnerStepResult` facts so reports can show both the primary normal-step failure and any cleanup failure. A normal-step failure must not cause subsequent normal business steps to run, but it must not prevent teardown steps from running.

The first sequence runner does not implement retry, timeout enforcement, optional/non-blocking semantics, manifest writing, CLI integration, report generation, or platform-driver construction. Those are later batches and should reuse the same shared events and evidence bundle contracts.

The first evidence implementation exposes a narrow API:

```python
recorder = EvidenceRecorder(run_id="run-1", output_dir=run_dir)
recorder.record_event(event)
recorder.record_step_result(result)
bundle = recorder.build_bundle()
manifest_path = recorder.write_manifest()
```

`EvidenceRecorder` stores historical execution facts. It must not execute actions, retry steps, classify case success, or know platform-specific driver behavior. Manifest writing should serialize model-owned contracts with `model_dump(mode="json")` and write below the caller-provided output directory.

The first artifact-store implementation exposes a narrow API:

```python
store = ArtifactStore(run_dir=Path("runs/run-1"))
ref = store.write_json(kind="ui_tree", step_id="step-1", phase="finalize", name="ui-tree", payload=ui_tree)
ref = store.write_text(kind="log", step_id="step-1", phase="invoke", name="driver", text=log_text)
ref = store.write_bytes(kind="screenshot", step_id="step-1", phase="finalize", name="screen", data=image_bytes)
```

`ArtifactStore` owns directory policy and filename normalization. It should create this run-local structure as needed:

```text
<run_dir>/
  evidence-manifest.json
  artifacts/
    screenshots/
    ui-trees/
    harness-calls/
    logs/
    raw/
```

Artifact refs returned by `ArtifactStore` should use paths relative to `run_dir`, for example `artifacts/screenshots/step-1-finalize-screen.png`. This keeps `EvidenceBundle` portable when a run directory is moved. `EvidenceRecorder` should consume these refs; it should not decide artifact subdirectories or write screenshot/UI-tree/log files itself.

Future Android platform support should use a two-layer extension model:

```text
StepRunner
  -> HarnessInterface
      -> AndroidHarness          # FSQ built-in runner-facing harness
          -> AndroidDriverInterface
              -> AppiumDriver
              -> UiAutomator2Driver
              -> UserCustomDriver
```

In this model, `AndroidHarness` implements `HarnessInterface` and owns FSQ runner-facing behavior: action dispatch from `ExecutableStep.action_name`, conversion to `HarnessActionResult`, context shaping, artifact refs, evidence policy entry points, and failure category mapping. Users who want to replace the underlying automation backend should implement `AndroidDriverInterface` instead of reimplementing `HarnessInterface` directly.

Platform harnesses are FSQ-controlled adapters, not independent platform runners. The execution protocol must stay platform-neutral and owned by FSQ: `StepRunner` controls `prepare -> invoke -> finalize`, emits `RunnerEvent` records, and provides the event/result stream consumed by `EvidenceRecorder`. Platform harnesses may translate FSQ actions into backend driver calls and shape platform context, but they must not own retry policy, event emission, evidence manifest structure, artifact directory policy, case result aggregation, or report generation.

Driver interfaces are thinner than harnesses. A driver implementation may execute backend actions and return raw platform observations such as screenshots, UI trees, logs, window/app state, or driver call metadata. It must not decide when artifacts are captured, where artifacts are stored, how evidence bundles are structured, or how runner phases are ordered. Those decisions remain in FSQ-owned runner, harness, evidence, and artifact-store code so Android, iOS, desktop, web, and future platforms produce consistent execution history and replayable evidence.

`AndroidDriverInterface` should be aligned with the FSQ AI Test DSL command vocabulary instead of exposing unrelated low-level primitive names. `AndroidHarness` dispatches from `ExecutableStep.action_name` using the original FSQ command name, while the Python driver protocol uses the corresponding snake_case method name. This keeps testcase actions, harness dispatch, and backend implementation visually traceable, while still allowing Appium, uiautomator2, MCP, or user drivers to implement the actual platform mechanics differently.

The complete FSQ AI Test DSL command set recognized by the Android harness design is:

```text
launchApp, stopApp, killApp, clearState, setPermissions,
tapOn, doubleTapOn, longPressOn, rightClickOn, hoverOn,
inputText, clearText, pressKey, swipe, scrollUntilVisible, scroll,
assertVisible, assertNotVisible, assert, assertWithAI,
waitUntil, waitForAnimationToEnd,
performActions, releaseActions, executeMethod,
runFlow, repeat, retry,
takeScreenshot, startRecording, stopRecording
```

The first Android contract implementation is limited to the commands currently used by the Android FSQ testcase corpus. The phase-1 driver protocol is synchronous and backend-free:

```python
class AndroidDriverInterface(Protocol):
    def context(self) -> dict[str, object]: ...
    def launch_app(self, params: dict[str, object]) -> dict[str, object]: ...
    def kill_app(self, params: dict[str, object]) -> dict[str, object]: ...
    def tap_on(self, params: dict[str, object]) -> dict[str, object]: ...
    def long_press_on(self, params: dict[str, object]) -> dict[str, object]: ...
    def input_text(self, params: dict[str, object]) -> dict[str, object]: ...
    def press_key(self, params: dict[str, object]) -> dict[str, object]: ...
    def swipe(self, params: dict[str, object]) -> dict[str, object]: ...
    def perform_actions(self, params: dict[str, object]) -> dict[str, object]: ...
    def assert_visible(self, params: dict[str, object]) -> dict[str, object]: ...
    def assert_not_visible(self, params: dict[str, object]) -> dict[str, object]: ...
    def assert_state(self, params: dict[str, object]) -> dict[str, object]: ...
    def assert_with_ai(self, params: dict[str, object]) -> dict[str, object]: ...
    def screenshot(self) -> bytes: ...
    def ui_tree(self) -> dict[str, object]: ...
```

The phase-1 dispatch table is:

| FSQ action | Driver method | Phase-1 parameter shape |
|---|---|---|
| `launchApp` | `launch_app` | bare command, normalized to `{}` |
| `killApp` | `kill_app` | bare command, normalized to `{}` |
| `tapOn` | `tap_on` | `{target, locator, timeout?}` |
| `assertVisible` | `assert_visible` | `{target, locator, optional?, timeout?}` |
| `performActions` | `perform_actions` | W3C actions array, passed as `{"actions": [...]}` |
| `assert` | `assert_state` | `{element, text, optional}` |
| `pressKey` | `press_key` | string shorthand normalized to `{"key": "Back"}` or object form |
| `inputText` | `input_text` | `{text, target, locator}` |
| `assertNotVisible` | `assert_not_visible` | `{target, locator, optional?}` |
| `longPressOn` | `long_press_on` | `{target, locator}` |
| `swipe` | `swipe` | `{direction, duration}` or future point form |
| `assertWithAI` | `assert_with_ai` | `{prompt, optional, timeout?}` |

`AndroidHarness(driver=driver, artifact_store=store | None)` should satisfy `HarnessInterface`. Its first action dispatcher should support exactly the phase-1 FSQ action names above. Screenshot and UI-tree capture should be available through `capture_artifact`; when an `ArtifactStore` is provided, screenshots and UI trees should be written to the standard artifact directories and returned as `HarnessArtifactRef` values. `capture_artifact` must receive FSQ-owned evidence metadata such as `step_id` and `phase` from the caller and must not infer those values from Android session context. Unsupported actions from the complete command set should return a failed `HarnessActionResult` with `failure_category="configuration_error"` rather than calling the driver until their driver methods are specified and implemented.

The first concrete backend implementation is `UiAutomator2AndroidDriver`. It should satisfy `AndroidDriverInterface` and remain narrower than `AndroidHarness`:

```python
driver = UiAutomator2AndroidDriver(app_id="com.microsoft.emmx", serial="device-1")
driver = UiAutomator2AndroidDriver(app_id="com.microsoft.emmx", device=fake_device)
```

`device` injection is required for unit tests and local backend adapters that already own a uiautomator2 device object. If `device` is omitted, the driver imports `uiautomator2` lazily and calls `uiautomator2.connect(serial)`. Missing `uiautomator2` must raise `ConfigurationError` with installation guidance for the optional `android` extra rather than failing at package import time.

The phase-1 `UiAutomator2AndroidDriver` should implement only the existing `AndroidDriverInterface` methods. It may translate FSQ locator payloads to uiautomator2 selectors using these first rules:

| FSQ locator field | uiautomator2 selector behavior |
|---|---|
| `resourceId` | `device(resourceId=value)` |
| `accessibilityId` | `device(description=value)` |
| `text` | `device(text=value)` |
| `className` | `device(className=value)` |
| `xpath` | `device.xpath(value)` |
| missing locator with `target` or scalar `value` | text selector fallback |

Backend methods should return driver output dictionaries that `AndroidHarness` can convert into `HarnessActionResult`. Target lookup failures should return `status="failed"`, `failure_category="target_resolution_error"`, and a concise error message. Unsupported or underspecified backend operations should return `status="failed"` with `failure_category="configuration_error"`. The driver should not raise for ordinary target/assertion misses, decide retry policy, write artifacts, emit runner events, or aggregate case results.

`UiAutomator2AndroidDriver` owns deterministic Android element wait policy for backend target resolution. FSQ YAML should not carry per-step wait durations for this phase-1 strict path; action payloads remain focused on user intent and locators. The first implementation should use a fixed internal default element wait timeout of `10.0` seconds and should prefer uiautomator2's built-in wait APIs over custom polling:

- `UiObject.wait(exists=True, timeout=10.0)` for ordinary selector existence.
- `UiObject.wait_gone(timeout=10.0)` for ordinary selector disappearance.
- `DeviceXPathSelector.wait(timeout=10.0)` for XPath selector existence, because XPath wait does not accept `exists=True`.

The first waiting behavior applies to target-bearing driver methods: `tap_on`, `long_press_on`, `input_text`, `assert_visible`, and `assert_state`. These methods should wait for the authored selector before returning `target_resolution_error`. `assert_not_visible` should pass immediately if the target is already absent, wait up to the same default timeout when the target is currently visible, and fail with `failure_category="assertion_error"` if the target remains visible. This wait policy is not locator fallback, self-healing, or AI recovery; it waits only for the same authored selector and preserves strict failure when the selector does not resolve within the driver timeout.

`assert_with_ai` remains a placeholder backend assertion in phase 1. It should return a failed configuration result explaining that AI visual assertion is not implemented in the uiautomator2 backend yet; later visual-verification work should consume screenshots through FSQ-owned evidence and verification layers.

Strict regression and recovery execution must remain explicit modes at the entry/regression orchestration layer. The default deterministic core path is strict: it executes `ExecutableStep` locator/action payloads as authored and records failures without AI, locator fallback, or testcase mutation. Recovery mode may later enable deterministic locator fallback or AI-assisted repair, but it must be invoked as a separate recovery run with separate evidence. `StepRunner`, `StepSequenceRunner`, `AndroidHarness`, and drivers must not silently convert a strict target miss into a recovered pass.

## Internal Structure

Planned structure after the first implementation batch:

- `__init__.py`: Public exports only.
- `runner/__init__.py`: Runner subpackage exports only.
- `runner/_runner.py`: `StepRunner` implementation for the minimal single-step protocol.
- `runner/_sequence.py`: `StepSequenceRunner` implementation for ordered `ExecutableStep` execution and evidence recording.
- `harness/__init__.py`: Harness subpackage exports only.
- `harness/_interface.py`: `HarnessInterface` protocol.
- `harness/_android.py`: Future FSQ built-in `AndroidHarness` implementation that satisfies `HarnessInterface`.
- `harness/_android_driver.py`: Future `AndroidDriverInterface` protocol and driver-owned primitive contracts.
- `harness/_uiautomator2_driver.py`: Optional uiautomator2 backend implementation of `AndroidDriverInterface` with lazy dependency import and fake-device injection for tests.
- `evidence/__init__.py`: Evidence subpackage exports only.
- `evidence/_recorder.py`: `EvidenceRecorder` implementation.
- `evidence/_artifact_store.py`: `ArtifactStore` implementation for run-local artifact paths and file writing.
- `SPEC.md`: Module design.

The core module must not define Pydantic models that are shared across modules. Shared models belong in `fsq_agent.models` according to the project guide.

## Error Handling

Core orchestration code should convert phase-level exceptions into shared structured result models owned by `models`. It should not introduce custom exceptions in this module. Any new project-wide exception class must be defined in `fsq_agent.models` and documented in `fsq_agent/models/SPEC.md` first.

Runner phases should preserve failure boundaries:

- prepare failures: context, setup, validation, or before-action observation failures
- invoke failures: action, target, timeout, platform command, or assertion failures
- finalize failures: after-action observation, artifact capture, stabilization, or cleanup failures

## Design Decisions

- `core` owns execution control boundaries, not shared data models.
- `models` owns serializable execution contracts, result records, runner events, harness context/result records, evidence manifests, and status/failure taxonomies.
- `HarnessInterface` is a protocol because it represents platform capability rather than persisted data.
- `HarnessInterface` is the runner-facing harness contract. It is intentionally higher-level than a raw Appium, Playwright, uiautomator2, or Midscene-style primitive interface.
- `StepRunner` should call harness capabilities through `HarnessInterface`, emit shared runner events, and return shared step result models.
- The minimal runner slice is synchronous. Async support should be decided when real MCP/Appium/Playwright harness integration is planned.
- Fake harnesses for the minimal runner slice should live in tests until a reusable product fake is needed.
- FSQ should provide a built-in `AndroidHarness` for Android execution semantics. Extension users who want uiautomator2, Appium, MCP, or another backend should usually implement `AndroidDriverInterface`, not a full custom `HarnessInterface`.
- Platform harnesses should remain FSQ-owned controlled adapters. They may handle platform action translation, context shaping, driver-result conversion, and failure-category mapping, but not runner ordering, retry policy, event emission, evidence manifest format, artifact path policy, case-level result aggregation, or report generation.
- Driver interfaces should remain backend mechanics contracts. They may execute actions and expose raw observations, but not control when evidence is captured or how execution history is recorded.
- Locator self-healing is not part of strict execution. Any deterministic fallback or AI-assisted repair must be represented as recovery execution so reports can compare strict truth with recovery outcome.
- Direct custom `HarnessInterface` implementations should remain possible for advanced platform plugins, but they are not the preferred ordinary Android backend extension point.
- `EvidenceRecorder` should consume shared runner events and result facts. It should not execute actions, retry steps, or decide case success.
- The first `EvidenceRecorder` writes one manifest file and references artifact paths supplied by events/results. It does not copy binary artifacts or generate reports.
- `ArtifactStore` owns evidence directory layout and artifact file writing. Harnesses, drivers, and future evidence policies should ask `ArtifactStore` for artifact refs instead of constructing paths manually.
- Artifact paths in model refs should be relative to the run directory unless a later external storage backend requires URI-style refs.
- Concrete Android/Web/iOS harness implementations are out of scope for the first contract batch and must not be placed in `core`.
- CLI, report generation, verifier behavior, planner repair, and FSQ StepBuilder integration are later batches.
