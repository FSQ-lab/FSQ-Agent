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
- `EvidenceRecorder`: Event/result sink that builds an `EvidenceBundle` and writes a JSON manifest for execution facts and artifact references.
- `ArtifactStore`: Evidence artifact path policy and writer for run-local screenshots, UI trees, harness-call JSON, logs, and raw files.

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

`AndroidDriverInterface` should represent lower-level Android primitives such as tap/click, text input, screenshot capture, UI tree capture, back, scroll, wait/stabilize, and backend-specific error exposure. This layer is closer to Midscene's low-level interface concept, while `HarnessInterface` remains the higher-level runner-facing harness contract.

The first Android contract implementation should stay backend-free and expose only a small synchronous driver protocol:

```python
class AndroidDriverInterface(Protocol):
    def context(self) -> dict[str, object]: ...
    def tap(self, params: dict[str, object]) -> dict[str, object]: ...
    def input_text(self, params: dict[str, object]) -> dict[str, object]: ...
    def back(self) -> dict[str, object]: ...
    def screenshot(self) -> bytes: ...
    def ui_tree(self) -> dict[str, object]: ...
```

`AndroidHarness(driver=driver, artifact_store=store | None)` should satisfy `HarnessInterface`. Its first action dispatcher should support `tap`, `inputText`, and `back`. Screenshot and UI-tree capture should be available through `capture_artifact`; when an `ArtifactStore` is provided, screenshots and UI trees should be written to the standard artifact directories and returned as `HarnessArtifactRef` values. Unsupported actions should return a failed `HarnessActionResult` with `failure_category="configuration_error"` rather than calling the driver.

## Internal Structure

Planned structure after the first implementation batch:

- `__init__.py`: Public exports only.
- `runner/__init__.py`: Runner subpackage exports only.
- `runner/_runner.py`: `StepRunner` implementation for the minimal single-step protocol.
- `harness/__init__.py`: Harness subpackage exports only.
- `harness/_interface.py`: `HarnessInterface` protocol.
- `harness/_android.py`: Future FSQ built-in `AndroidHarness` implementation that satisfies `HarnessInterface`.
- `harness/_android_driver.py`: Future `AndroidDriverInterface` protocol and driver-owned primitive contracts.
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
- Direct custom `HarnessInterface` implementations should remain possible for advanced platform plugins, but they are not the preferred ordinary Android backend extension point.
- `EvidenceRecorder` should consume shared runner events and result facts. It should not execute actions, retry steps, or decide case success.
- The first `EvidenceRecorder` writes one manifest file and references artifact paths supplied by events/results. It does not copy binary artifacts or generate reports.
- `ArtifactStore` owns evidence directory layout and artifact file writing. Harnesses, drivers, and future evidence policies should ask `ArtifactStore` for artifact refs instead of constructing paths manually.
- Artifact paths in model refs should be relative to the run directory unless a later external storage backend requires URI-style refs.
- Concrete Android/Web/iOS harness implementations are out of scope for the first contract batch and must not be placed in `core`.
- CLI, report generation, verifier behavior, planner repair, and FSQ StepBuilder integration are later batches.
