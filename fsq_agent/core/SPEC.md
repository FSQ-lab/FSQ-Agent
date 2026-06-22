# Module: core

## Purpose

Define the shared execution-core orchestration layer for FSQ-Agent. The core module owns the StepRunner protocol boundary, core-owned pure wait execution, harness capability interface, and evidence-recording coordination points that will let FSQ YAML execution and natural-goal execution converge before platform operations.

The module remains implementation-first only after SPEC confirmation. Public strict-core CLI orchestration belongs to `cli`; this module owns deterministic execution contracts and must stay independent from CLI command parsing.

## Dependencies

- `models`: Uses shared execution-core data structures such as executable steps, pure wait parameter models, phase reports, runner events, harness context/results, artifact refs, evidence bundle manifests, execution failure/status literals, serializable harness function schemas, Android driver parameter models, and AI assertion request/result models.

The core module must not depend on `agent`, `providers`, `tools`, `cli`, `fsq`, `report`, `observation`, `knowledge`, `skills`, or concrete platform tool modules in its first contract batch.

## Public Interface

Planned `__init__.py` exports via `__all__`:

- `HarnessInterface`: Protocol describing platform capabilities required by StepRunner. Concrete Android, Web, iOS, and fake harnesses may satisfy the protocol structurally.
- `StepRunner`: Minimal synchronous runner that executes one `ExecutableStep` through the `prepare`, `invoke`, and `finalize` phases using a supplied `HarnessInterface`.
- `StepSequenceRunner`: Minimal synchronous runner that executes an ordered list of `ExecutableStep` records with `StepRunner`, records events and step results, and builds an `EvidenceBundle` through `EvidenceRecorder`.
- `EvidenceRecorder`: Event/result sink that builds an `EvidenceBundle` and writes a JSON manifest for execution facts and artifact references.
- `ArtifactStore`: Evidence artifact path policy and writer for run-local screenshots, UI trees, harness-call JSON, logs, and raw files.
- `AIAssertionEvaluatorProtocol`: Structural protocol for provider-backed visual assertion evaluation. It accepts serializable `AIAssertionRequest` values and returns `AIAssertionResult` values without exposing provider runtime objects to `core`.
- `AndroidDriverInterface`: Protocol describing the typed Android backend driver methods that `AndroidHarness` may call.
- `AndroidHarness`: Built-in Android runner-facing harness that satisfies `HarnessInterface`, dispatches authored FSQ action names to Android driver methods or harness-owned platform assertion handlers, validates action payloads with shared Pydantic models, converts driver/evaluator output into `HarnessActionResult`, and owns Android artifact capture integration.
- `UiAutomator2AndroidDriver`: Optional Android backend driver that satisfies `AndroidDriverInterface` using uiautomator2 when the `android` extra is installed.

Planned subpackage exports:

- `fsq_agent.core.runner`: Home for `StepRunner` and runner orchestration helpers. It imports shared runner models from `fsq_agent.models` rather than defining cross-module data models locally.
- `fsq_agent.core.harness`: Home for `HarnessInterface`, `AIAssertionEvaluatorProtocol`, Android harness/driver contracts, concrete Android backend implementations, and harness-neutral driver-tool schema helpers. It imports shared harness, Android parameter models, and AI assertion models from `fsq_agent.models`. Its public subpackage exports include `HarnessInterface`, `AIAssertionEvaluatorProtocol`, `AndroidDriverInterface`, `AndroidHarness`, `UiAutomator2AndroidDriver`, and `driver_tool`.
- `fsq_agent.core.evidence`: Home for `EvidenceRecorder`, `ArtifactStore`, and evidence coordination logic. It imports evidence bundle and artifact models from `fsq_agent.models`.

The first runner implementation exposes a narrow synchronous API:

```python
runner = StepRunner(harness=harness)
result = runner.run_step(run_id="run-1", step=executable_step)
events = runner.events
```

`StepRunner` accepts any object satisfying `HarnessInterface`. Entry-layer code and future factories are responsible for constructing platform-specific harnesses such as Android, Web, iOS, or fake harnesses.

`StepRunner` also handles core-owned `waitMs` steps. A step with `action_name="waitMs"` must validate `step.params` with `WaitMsParams`, execute a pure elapsed-time wait, emit ordinary runner phase/step events, and return a passed `RunnerStepResult` without calling `HarnessInterface.get_context()`, `before_action`, `invoke_action`, `after_action`, or `capture_artifact`. A malformed `waitMs` payload returns a structured failed result with `failure_category="configuration_error"`. Pure waits must not route through Android driver gestures, CommonTool execution, or platform harness actions.

`HarnessInterface.action_space()` returns `list[HarnessFunctionSchema]`. Each schema describes one concrete platform harness or driver action that the harness can expose as an OpenAI-compatible function schema for both strict-core metadata and the goal-driven agent loop. It must return serializable schema data only; it must not construct OpenAI Agents SDK `FunctionTool` objects. Tool names in this action space are handler/driver method names such as `tap_on`, `input_text`, and `assert_with_ai`, not FSQ action names such as `tapOn`, `inputText`, or `assertWithAI`. When available, schemas should include `fsq_action_name` metadata so reports and adapters can relate platform methods back to authored FSQ actions. Schemas for reviewed driver tools that should receive dynamic before/after evidence should set `capture_evidence=True`; unreviewed, read-only, assertion, or observation tools should keep the default `False`.

`StepRunner` owns evidence-policy timing. When `ExecutableStep.evidence_policy` requests artifact capture, the runner should call `HarnessInterface.capture_artifact` with FSQ-owned `step_id`, `phase`, and a stable reason string. The first evidence-policy implementation should support:

- `capture_before=True`: capture requested `artifact_kinds` during the `prepare` phase after context is available and before `before_action` completes.
- `capture_after=True`: capture requested `artifact_kinds` during the `finalize` phase after `after_action` completes.
- `capture_on_failure=True`: when invoke returns or raises a failure, capture requested `artifact_kinds` during `finalize` with a failure reason.
- `artifact_kinds`: only `screenshot` and `ui_tree` are required in the first implementation. Unsupported kinds should not crash the runner; they should produce a failed finalize phase report with `failure_category="artifact_error"` and a useful error message.

Captured artifact refs should be attached to the corresponding `StepPhaseReport.artifact_refs`, and every successful capture should emit a `RunnerEvent(event_type="artifact_captured")` with payload fields for `artifact_id`, `kind`, `path`, `reason`, and `phase`. The runner must not decide artifact directories or serialize binary data; `HarnessInterface` and `ArtifactStore` handle raw capture and path policy.

The first sequence runner implementation exposes a narrow synchronous API:

```python
runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder, step_interval_seconds=1.0)
result = runner.run_steps(run_id="run-1", steps=executable_steps, teardown_steps=teardown_steps)
```

`StepSequenceRunner` accepts only shared `ExecutableStep` records and must not import `fsq`, parse YAML, construct platform drivers, resolve strict replay refs, or generate reports. Its first behavior is intentionally small:

- Run normal steps in list order by delegating each step to `StepRunner.run_step`.
- Record every event emitted by each `StepRunner` into the supplied `EvidenceRecorder`.
- Record every `RunnerStepResult` into the supplied `EvidenceRecorder`.
- Stop normal-step execution on the first step whose result status is `failed`, `cancelled`, or `skipped`.
- Always execute supplied `teardown_steps` after normal execution stops or completes, including after failed, cancelled, skipped, or exception-converted normal steps.
- Sleep for `step_interval_seconds` before each subsequent executed step when that interval is greater than zero, including between normal steps and before teardown steps when a prior step already ran. The default interval is one second, and entry layers may pass a configured non-negative interval such as `harness.strict_core.step_interval_seconds` without making `core` import or understand the config module. This pacing is not a `waitMs` FSQ command, must not call the harness, and must not add synthetic step results to evidence.
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

Driver interfaces are thinner than harnesses. A driver implementation may execute backend actions and return raw platform observations such as screenshots, UI trees, logs, window/app state, or driver call metadata. It must not decide when artifacts are captured, where artifacts are stored, how evidence bundles are structured, how runner phases are ordered, or whether a provider-backed AI assertion passes. Those decisions remain in FSQ-owned runner, harness, evidence, artifact-store, and injected evaluator code so Android, iOS, desktop, web, and future platforms produce consistent execution history and replayable evidence.

`AndroidDriverInterface` should be aligned with the FSQ AI Test DSL command vocabulary instead of exposing unrelated low-level primitive names for driver-owned actions. `AndroidHarness` dispatches from `ExecutableStep.action_name` using the original FSQ command name, while driver-owned actions use corresponding snake_case method names. Harness-owned actions such as `assertWithAI` also use snake_case handler names for action-space exposure, but they are not methods that Android drivers implement. This keeps testcase actions, harness dispatch, and backend implementation visually traceable, while still allowing direct Appium, uiautomator2, or user drivers to implement the actual platform mechanics differently.

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

Generated strict replay cases may also contain `waitMs`, but it is a core-owned pure wait command and is not part of the Android harness command set.

The first Android contract implementation is limited to the commands currently used by the Android FSQ testcase corpus. The phase-1 driver protocol is synchronous and backend-free:

```python
class AndroidDriverInterface(Protocol):
    def context(self) -> dict[str, object]: ...
    def launch_app(self, params: AndroidLaunchAppParams) -> dict[str, object]: ...
    def kill_app(self, params: AndroidKillAppParams) -> dict[str, object]: ...
    def tap_on(self, params: AndroidTapOnParams) -> dict[str, object]: ...
    def long_press_on(self, params: AndroidLongPressOnParams) -> dict[str, object]: ...
    def input_text(self, params: AndroidInputTextParams) -> dict[str, object]: ...
    def press_key(self, params: AndroidPressKeyParams) -> dict[str, object]: ...
    def swipe(self, params: AndroidSwipeParams) -> dict[str, object]: ...
    def perform_actions(self, params: AndroidPerformActionsParams) -> dict[str, object]: ...
    def assert_visible(self, params: AndroidAssertVisibleParams) -> dict[str, object]: ...
    def assert_not_visible(self, params: AndroidAssertNotVisibleParams) -> dict[str, object]: ...
    def assert_state(self, params: AndroidAssertStateParams) -> dict[str, object]: ...
    def ui_tree(self, params: AndroidUiTreeParams) -> dict[str, object]: ...
    def screenshot(self) -> bytes: ...
```

The phase-1 dispatch table is owned in code by the shared `ANDROID_ACTION_DEFINITIONS_BY_NAME` registry from `models`. `AndroidHarness`, FSQ executable-step conversion, and Android driver tool decoration must consume that registry instead of maintaining separate hand-written maps. Its current entries are:

| FSQ action | Handler/driver method | Owner | Phase-1 parameter shape |
|---|---|---|---|
| `launchApp` | `launch_app` | driver | `AndroidLaunchAppParams` |
| `killApp` | `kill_app` | driver | `AndroidKillAppParams` |
| `tapOn` | `tap_on` | driver | `AndroidTapOnParams` |
| `assertVisible` | `assert_visible` | driver | `AndroidAssertVisibleParams` |
| `performActions` | `perform_actions` | driver | `AndroidPerformActionsParams` |
| `assert` | `assert_state` | driver | `AndroidAssertStateParams` |
| `pressKey` | `press_key` | driver | `AndroidPressKeyParams` |
| `inputText` | `input_text` | driver | `AndroidInputTextParams` |
| `assertNotVisible` | `assert_not_visible` | driver | `AndroidAssertNotVisibleParams` |
| `longPressOn` | `long_press_on` | driver | `AndroidLongPressOnParams` |
| `swipe` | `swipe` | driver | `AndroidSwipeParams` |
| `uiTree` | `ui_tree` | driver | `AndroidUiTreeParams` |
| `assertWithAI` | `assert_with_ai` | harness | `AndroidAssertWithAIParams` |

`AndroidHarness` owns validation from resolved `ExecutableStep.params` dictionaries into the corresponding Android parameter model from `ANDROID_ACTION_DEFINITIONS_BY_NAME` before it calls a driver method or harness-owned handler. Strict replay refs such as `RuntimeSecretRef` must already be resolved by the entry layer before Android harness validation. Validation failures must return `HarnessActionResult(status="failed", failure_category="configuration_error")` before any driver method side effect or evaluator call. Driver-owned actions pass typed Pydantic parameter models to the concrete driver and convert driver output dictionaries into `HarnessActionResult`. Harness-owned `assertWithAI` captures the current screenshot through harness artifact capture, builds an `AIAssertionRequest`, invokes the injected `AIAssertionEvaluatorProtocol`, and converts `AIAssertionResult` into `HarnessActionResult` evidence.

Concrete driver methods opt in to action-space discovery by using `driver_tool` or an Android-specific internal wrapper that is backed by `ANDROID_ACTION_DEFINITIONS_BY_NAME`. `AndroidHarness.action_space()` is the public access point for discovered schemas. Internally, harness schema discovery should inspect `type(driver)` and return schemas for decorated driver methods plus harness-owned schemas such as `assert_with_ai` when the harness supports them. Generic `driver_tool` should infer the Pydantic parameter model from the method annotation unless the decorator supplies `params_model` explicitly. Android-specific decoration should verify that the concrete method name and `params` annotation match the shared action registry before attaching metadata. The Android-specific decorator should also accept `capture_evidence: bool = False` and carry that reviewed evidence-capture intent through driver-tool metadata into `HarnessFunctionSchema.capture_evidence`; dynamic agents consume the schema flag, while core remains independent of OpenAI Agents SDK behavior. A decorated method without a resolvable Pydantic model should fail schema discovery with `ConfigurationError`. Undecorated methods remain callable by strict harness dispatch if they are part of `AndroidDriverInterface`, but they do not appear in `action_space()`.

`AndroidHarness(driver=driver, artifact_store=store | None, ai_assertion_evaluator=evaluator | None)` should satisfy `HarnessInterface`. Its first action dispatcher should support exactly the phase-1 FSQ action names above. Screenshot and UI-tree capture should be available through `capture_artifact`; when an `ArtifactStore` is provided, screenshots and UI trees should be written to the standard artifact directories and returned as `HarnessArtifactRef` values. `capture_artifact` must receive FSQ-owned evidence metadata such as `step_id` and `phase` from the caller and must not infer those values from Android session context. The `uiTree` action is separate from artifact capture: it is a read-only driver-owned observation tool exposed to dynamic agents and should return the current UI hierarchy inline through the harness action result. Unsupported actions from the complete command set should return a failed `HarnessActionResult` with `failure_category="configuration_error"` rather than calling the driver until their driver methods are specified and implemented. Authored `assertWithAI` must fail with `failure_category="configuration_error"` when no evaluator is injected.

The first concrete backend implementation is `UiAutomator2AndroidDriver`. It should satisfy `AndroidDriverInterface` and remain narrower than `AndroidHarness`:

```python
driver = UiAutomator2AndroidDriver(app_id="com.microsoft.emmx", serial="device-1")
driver = UiAutomator2AndroidDriver(app_id="com.microsoft.emmx", device=fake_device)
```

`device` injection is required for unit tests and local backend adapters that already own a uiautomator2 device object. If `device` is omitted, the driver imports `uiautomator2` lazily and calls `uiautomator2.connect(serial)`. Missing `uiautomator2` must raise `ConfigurationError` with installation guidance for the optional `android` extra rather than failing at package import time.

The phase-1 `UiAutomator2AndroidDriver` should implement only the driver-owned `AndroidDriverInterface` methods. Its concrete function-call action space should decorate the backend methods it intentionally exposes. Phase-1 decorated methods should include `launch_app`, `kill_app`, `tap_on`, `long_press_on`, `input_text`, `press_key`, `swipe`, `assert_visible`, `assert_not_visible`, `assert_state`, and `ui_tree`. Reviewed UI-changing decorated methods `launch_app`, `kill_app`, `tap_on`, `long_press_on`, `input_text`, `press_key`, and `swipe` should declare `capture_evidence=True` on `_android_driver_tool(...)`; assertion and observation methods should keep the default `False`. Unsupported backend methods such as `perform_actions` should remain undecorated until the concrete backend owns a usable implementation, and adding an evidence flag must not expose an otherwise undecorated method. The driver may translate FSQ locator payloads to uiautomator2 selectors using these first rules:

| FSQ locator field | uiautomator2 selector behavior |
|---|---|
| `resourceId` | `device(resourceId=value)` |
| `accessibilityId` | `device(description=value)` |
| `text` | `device(text=value)` |
| `className` | `device(className=value)` |
| `xpath` | `device.xpath(value)` |
| missing locator with `target` | text selector fallback |

Backend methods should return driver output dictionaries that `AndroidHarness` can convert into `HarnessActionResult`. Target lookup failures should return `status="failed"`, `failure_category="target_resolution_error"`, and a concise error message. Unsupported or underspecified backend operations should return `status="failed"` with `failure_category="configuration_error"`. The driver should not raise for ordinary target/assertion misses, decide retry policy, write artifacts, emit runner events, or aggregate case results.

`AndroidDriverInterface.assert_state` is the Android platform assertion contract for FSQ `assert`. It should accept an `element` object that may contain locator fields plus expected Android state fields. Locator fields are used only for target resolution; expected state fields are evaluated after the element is found. Phase-1 text assertions remain supported through `text.contains` and `text.equals`. Phase-1 Android element-state assertions must support these boolean fields when present under `element`: `enabled`, `checked`, `selected`, `clickable`, and `focused`. Phase-1 element existence assertions must pass when `element` contains only supported locator fields and the element is found. A state mismatch should return `failure_category="assertion_error"`; an unsupported assertion shape should return `failure_category="configuration_error"`; target lookup failure should return `failure_category="target_resolution_error"`.

`UiAutomator2AndroidDriver.swipe` should support both direction-based and point-based FSQ payloads. Direction-based swipes compute points from the current screen size. Point-based swipes pass authored integer `start.x`, `start.y`, `end.x`, and `end.y` values directly to uiautomator2 with `duration` converted from milliseconds to seconds. Missing or malformed point payloads should return `configuration_error` rather than guessing coordinates.

`UiAutomator2AndroidDriver.input_text` should use a user-like focused input sequence for target-bearing text entry: wait for the authored selector, click it to focus, clear existing text when the backend selector exposes `clear_text`, then call `set_text(text)`. The backend should not silently fall back to AI or alternate locators when this sequence fails.

`UiAutomator2AndroidDriver` owns deterministic Android element wait policy for backend target resolution. FSQ YAML should not carry per-step wait durations for this phase-1 strict path; action payloads remain focused on user intent and locators. The first implementation should use a fixed internal default element wait timeout of `10.0` seconds and should prefer uiautomator2's built-in wait APIs over custom polling:

- `UiObject.wait(exists=True, timeout=10.0)` for ordinary selector existence.
- `UiObject.wait_gone(timeout=10.0)` for ordinary selector disappearance.
- `DeviceXPathSelector.wait(timeout=10.0)` for XPath selector existence, because XPath wait does not accept `exists=True`.

The first waiting behavior applies to target-bearing driver methods: `tap_on`, `long_press_on`, `input_text`, `assert_visible`, and `assert_state`. These methods should wait for the authored selector before returning `target_resolution_error`. `assert_not_visible` should pass immediately if the target is already absent, wait up to the same default timeout when the target is currently visible, and fail with `failure_category="assertion_error"` if the target remains visible. This wait policy is not locator fallback, self-healing, or AI recovery; it waits only for the same authored selector and preserves strict failure when the selector does not resolve within the driver timeout.

`assertWithAI` is an explicit visual assertion step, not recovery. It is a harness-owned Android platform assertion that may use an injected provider-backed `AIAssertionEvaluatorProtocol` in both dynamic and strict-core entry paths when the authored step explicitly requests it. `AndroidHarness` must capture a fresh screenshot artifact for the assertion, call the evaluator with an `AIAssertionRequest`, attach the returned `AIAssertionResult` metadata and screenshot ref to the `HarnessActionResult`, and fail the action with `failure_category="assertion_error"` when the verdict is negative. `UiAutomator2AndroidDriver` and other Android drivers must not call AI providers, attach images to model requests, decide visual verification, or expose `assert_with_ai` as a driver-owned schema. When no evaluator is injected, `AndroidHarness` must fail authored `assertWithAI` clearly with `failure_category="configuration_error"`.

Strict regression and recovery execution must remain explicit modes at the entry/regression orchestration layer. The default strict core path executes `ExecutableStep` locator/action payloads as authored and records failures without locator fallback, testcase mutation, or AI recovery. The only LLM/provider call allowed in strict execution is the explicit authored `assertWithAI` platform assertion when an evaluator has been injected. Recovery mode may later enable deterministic locator fallback or AI-assisted repair, but it must be invoked as a separate recovery run with separate evidence. `StepRunner`, `StepSequenceRunner`, `AndroidHarness`, and drivers must not silently convert a strict target miss into a recovered pass.

## Internal Structure

Planned structure after the first implementation batch:

- `__init__.py`: Public exports only.
- `runner/__init__.py`: Runner subpackage exports only.
- `runner/_runner.py`: `StepRunner` implementation for the minimal single-step protocol.
- `runner/_sequence.py`: `StepSequenceRunner` implementation for ordered `ExecutableStep` execution and evidence recording.
- `harness/__init__.py`: Harness subpackage exports only.
- `harness/_interface.py`: `HarnessInterface` and `AIAssertionEvaluatorProtocol` protocols.
- `harness/_android.py`: Future FSQ built-in `AndroidHarness` implementation that satisfies `HarnessInterface`.
- `harness/_android_driver.py`: Future `AndroidDriverInterface` protocol and driver-owned primitive contracts.
- `harness/_driver_tools.py`: Public `driver_tool` metadata decorator plus internal concrete-driver function schema discovery helpers used by harness implementations.
- `harness/_uiautomator2_driver.py`: Optional uiautomator2 backend implementation of `AndroidDriverInterface` with lazy dependency import and fake-device injection for tests.
- `evidence/__init__.py`: Evidence subpackage exports only.
- `evidence/_recorder.py`: `EvidenceRecorder` implementation.
- `evidence/_artifact_store.py`: `ArtifactStore` implementation for run-local artifact paths and file writing.
- `SPEC.md`: Module design.

The core module must not define Pydantic models that are shared across modules. Shared models belong in `fsq_agent.models` according to the project guide.

## Error Handling

Core orchestration code should convert phase-level exceptions into shared structured result models owned by `models`. It should not introduce custom exceptions in this module. Any new project-wide exception class must be defined in `fsq_agent.models` and documented in `fsq_agent/models/SPEC.md` first.

Harness action payload validation errors should be treated as configuration failures. `AndroidHarness` should validate parameters before calling a concrete driver method and return a structured failed `HarnessActionResult` instead of allowing malformed payloads to reach a backend side effect.

Driver action-space discovery errors, such as a decorated method with no Pydantic parameter model, should raise `ConfigurationError` from `models` so startup or diagnostics can report the broken concrete driver contract.

Runner phases should preserve failure boundaries:

- prepare failures: context, setup, validation, or before-action observation failures
- invoke failures: action, target, timeout, platform command, or assertion failures
- finalize failures: after-action observation, artifact capture, stabilization, or cleanup failures

## Design Decisions

- `core` owns execution control boundaries, including core-owned pure waits, not shared data models.
- `models` owns serializable execution contracts, result records, runner events, harness context/result records, evidence manifests, and status/failure taxonomies.
- `HarnessInterface` is a protocol because it represents platform capability rather than persisted data.
- `HarnessInterface` is the runner-facing harness contract. It is intentionally higher-level than a raw Appium, Playwright, uiautomator2, or Midscene-style primitive interface.
- `HarnessInterface.action_space()` is a function-schema capability surface, not an SDK tool factory. It returns serializable `HarnessFunctionSchema` models so `agent` can adapt them to OpenAI Agents SDK objects without adding SDK dependencies to `core`.
- `AIAssertionEvaluatorProtocol` is structural and provider-neutral. `core` accepts an evaluator object but never constructs Azure OpenAI, GitHub Copilot, OpenAI Agents SDK, or Responses API clients.
- `StepRunner` should call harness capabilities through `HarnessInterface`, emit shared runner events, and return shared step result models.
- `StepRunner` should execute `waitMs` internally as a deterministic elapsed-time wait and should not expose it through harness action-space discovery or concrete Android drivers.
- The minimal runner slice is synchronous. Async support should be decided when real direct Appium, uiautomator2, Playwright, or other harness driver integration requires it.
- Fake harnesses for the minimal runner slice should live in tests until a reusable product fake is needed.
- FSQ should provide a built-in `AndroidHarness` for Android execution semantics. Extension users who want uiautomator2, direct Appium, or another backend should usually implement `AndroidDriverInterface`, not a full custom `HarnessInterface`.
- Platform harnesses should remain FSQ-owned controlled adapters. They may handle platform action translation, context shaping, driver-result conversion, and failure-category mapping, but not runner ordering, retry policy, event emission, evidence manifest format, artifact path policy, case-level result aggregation, or report generation.
- Driver interfaces should remain backend mechanics contracts. They may execute actions and expose raw observations, but not control when evidence is captured or how execution history is recorded.
- Concrete drivers control their function-call exposure by decorating methods with `driver_tool`. An interface method existing in `AndroidDriverInterface` is not enough to expose that method in `action_space()`. Harness-owned schemas such as Android `assert_with_ai` are exposed by `AndroidHarness`, not by concrete drivers.
- Concrete driver-tool declarations own reviewed dynamic evidence-capture intent for exposed driver methods. The Android-specific wrapper around `driver_tool` carries `capture_evidence=True` into `HarnessFunctionSchema.capture_evidence`; core only propagates this typed schema flag and does not construct `EvidencePolicy` objects for dynamic agent runs.
- Android action parameter models are shared model contracts. `fsq` uses them to normalize YAML, `core` uses them to validate dispatch and generate function schemas, and concrete drivers use typed instances instead of raw dictionaries.
- Strict replay secret refs are not Android action parameter values. Entry-layer code must resolve them before `AndroidHarness` validates and dispatches actions, and core evidence must not persist resolved secret values.
- Android `assertWithAI` is explicit assertion evaluation. It may call an injected evaluator only because the authored step requested AI assertion; it must not be used for locator fallback, action repair, screenshot reinspection of unrelated steps, or testcase mutation.
- Locator self-healing is not part of strict execution. Any deterministic fallback or AI-assisted repair must be represented as recovery execution so reports can compare strict truth with recovery outcome.
- Direct custom `HarnessInterface` implementations should remain possible for advanced platform plugins, but they are not the preferred ordinary Android backend extension point.
- `EvidenceRecorder` should consume shared runner events and result facts. It should not execute actions, retry steps, or decide case success.
- The first `EvidenceRecorder` writes one manifest file and references artifact paths supplied by events/results. It does not copy binary artifacts or generate reports.
- `ArtifactStore` owns evidence directory layout and artifact file writing. Harnesses, drivers, and future evidence policies should ask `ArtifactStore` for artifact refs instead of constructing paths manually.
- Artifact paths in model refs should be relative to the run directory unless a later external storage backend requires URI-style refs.
- Concrete Android/Web/iOS harness implementations are out of scope for the first contract batch and must not be placed in `core`.
- CLI command parsing, LLM verification, planner repair, and FSQ loading remain outside `core`. Report generation is a separate `report` concern that consumes persisted evidence manifests.
