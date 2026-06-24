# Module: core

## Purpose

Define the shared execution-core orchestration layer for FSQ-Agent. The core module owns `StepRunner` as the single execution manager for canonical capability invocations, `StepSequenceRunner` ordering, harness and driver protocols, capability executor routing, and evidence-recording coordination points used by strict replay and dynamic execution.

The module does not parse CLI arguments, parse FSQ YAML, construct provider sessions, construct OpenAI Agents SDK tools, or generate reports. Entry modules build settings, providers, registries, and concrete harnesses, then pass registry snapshots and executor bindings into core.

## Dependencies

- Internal project dependencies: `models` and `capabilities` only.
- External dependencies: standard library typing/time/path modules and optional platform backend imports only inside concrete backend modules with lazy import behavior.
- Forbidden dependencies: `agent`, `providers`, `tools`, `cli`, `fsq`, `report`, `observation`, `knowledge`, `skills`, and OpenAI Agents SDK runtime types.

Core may consume `CapabilityDefinition`, `CapabilityInvocation`, `CapabilityExecutionResult`, `ReplayPolicy`, `ExecutableStep`, `EvidencePolicy`, runner result/event models, harness result/context models, Android parameter models, AI assertion models, and project exceptions from `models`.
Core may consume shared declaration decorators, platform action catalog helpers, and side-effect-free capability discovery helpers from `capabilities`. Core must not place execution behavior in `capabilities` or import CommonTool implementations from `tools`.

## Public Interface

Target `__init__.py` exports via `__all__`:

- `CapabilityRegistry`: Validated runtime registry for decorated capabilities. It resolves canonical names and aliases, rejects duplicate names and ambiguous aliases, exposes serializable snapshots, and validates that every capability has a parameter model/schema and executor binding.
- `CapabilityExecutorBindings`: Lightweight binding object or protocol containing executor implementations for `common`, `harness`, and `driver` capability kinds.
- `HarnessInterface`: Protocol describing platform capabilities required by StepRunner. Concrete Android, Web, iOS, and fake harnesses may satisfy the protocol structurally.
- `StepRunner`: Executes one canonical `ExecutableStep` or capability invocation by looking up metadata in `CapabilityRegistry`, validating params with the declared model, applying evidence and sensitivity policy, routing through the appropriate executor binding, normalizing backend output, emitting structured safe events, and returning `RunnerStepResult`.
- `StepSequenceRunner`: Executes ordered `ExecutableStep` records with `StepRunner`, records events and step results, respects strict pacing, stops normal execution on blocking failures, and always executes supplied teardown steps.
- `EvidenceRecorder`: Event/result sink that builds an `EvidenceBundle` and writes a JSON manifest for execution facts and artifact references.
- `ArtifactStore`: Evidence artifact path policy and writer for run-local screenshots, UI trees, harness-call JSON, logs, and raw files.
- `AIAssertionEvaluatorProtocol`: Structural protocol for provider-backed visual assertion evaluation. It accepts serializable `AIAssertionRequest` values and returns `AIAssertionResult` values without exposing provider runtime objects to `core`.
- `AndroidDriverInterface`: Protocol describing typed Android backend driver methods that Android driver capabilities may call.
- `AndroidHarness`: Built-in Android runner-facing harness that satisfies `HarnessInterface`, hosts harness-owned capabilities such as `assert_with_ai`, routes driver capabilities to `AndroidDriverInterface`, validates action payloads with shared Pydantic models, converts driver/evaluator output into `HarnessActionResult`, and owns Android artifact capture integration.
- `UiAutomator2AndroidDriver`: Optional Android backend driver that satisfies `AndroidDriverInterface` using uiautomator2 when the `android` extra is installed.
- `driver_tool` compatibility helper and catalog-backed platform driver declaration helpers: Decorate concrete backend methods with capability metadata using the shared `capabilities` declaration layer; they do not execute or register capabilities by themselves. Android-specific behavior is represented by Android action catalog entries rather than a unique decorator implementation.

Planned subpackage exports:

- `fsq_agent.core.registry`: `CapabilityRegistry`, registry validation, alias resolution, and registry snapshots.
- `fsq_agent.core.runner`: `StepRunner`, executor binding protocols, and sequence runner orchestration.
- `fsq_agent.core.harness`: `HarnessInterface`, `AIAssertionEvaluatorProtocol`, Android harness/driver contracts, concrete Android backend implementations, and thin driver declaration helpers backed by `capabilities`.
- `fsq_agent.core.evidence`: `EvidenceRecorder`, `ArtifactStore`, and evidence coordination logic.

`StepRunner` exposes a narrow API:

```python
runner = StepRunner(registry=registry, executors=executors, harness=harness)
result = runner.run_step(run_id="run-1", step=executable_step)
events = runner.events
```

`ExecutableStep.action_name` stores the canonical capability name, such as `wait_ms`, `get_runtime_secret`, `tap_on`, `input_text`, or `assert_with_ai`. Authored names such as `waitMs`, `tapOn`, and `assertWithAI` are preserved in step metadata by parsers and adapters.

For each invocation, `StepRunner` must:

1. Resolve the canonical capability from the registry.
2. Validate params with `capability.params_model`.
3. Build safe invocation context containing run id, step id, source ref, authored action metadata, and capability metadata.
4. Derive the effective evidence policy from capability metadata and any explicit step policy. For harness and driver capabilities with `CapabilityDefinition.capture_evidence=True` and the default `EvidencePolicy()`, the effective policy must capture `screenshot` and `ui_tree` artifacts before the action, after the action, and on failure. A non-default `ExecutableStep.evidence_policy` is explicit and must not be overwritten by capability metadata.
5. Route by `executor_kind`: `common` to the CommonTool executor binding, `harness` to a harness-owned handler, and `driver` through the active harness to the platform driver/backend.
6. Normalize backend output into the shared runner result contract.
7. Apply sensitivity rules before persistence.
8. Emit structured events containing safe capability metadata, replay payload fields, artifact refs, and status.
9. Return `RunnerStepResult`.

`StepRunner` must not contain action-name branches for `waitMs`, `wait_ms`, `get_runtime_secret`, Android action names, or evidence-enabled Android mutations. A pure wait is a `common` capability with no harness context requirement. Runtime secret lookup is a sensitive `common` capability.

`StepSequenceRunner` exposes a narrow API:

```python
runner = StepSequenceRunner(step_runner=runner, evidence_recorder=recorder, step_interval_seconds=1.0)
bundle = runner.run_steps(run_id="run-1", steps=steps, teardown_steps=teardown_steps)
```

It must not import `fsq`, parse YAML, construct platform drivers, resolve strict replay refs, generate reports, or add synthetic `waitMs` steps for pacing.

`HarnessInterface` provides runner-facing behavior for context, artifact capture, and harness/driver capability execution. Platform harnesses are FSQ-controlled adapters; drivers execute backend mechanics and return raw platform observations. Harnesses and drivers do not decide runner ordering, retry policy, event emission, evidence manifest structure, artifact directory policy, case aggregation, or report generation.

Android LLM-exposed uiautomator2 capabilities in this SPEC cycle include canonical names such as `launch_app`, `kill_app`, `tap_on`, `long_press_on`, `input_text`, `press_key`, `swipe`, `assert_visible`, `assert_not_visible`, `assert_state`, `ui_tree`, and harness-owned `assert_with_ai`. Authored FSQ aliases include `launchApp`, `killApp`, `tapOn`, `longPressOn`, `inputText`, `pressKey`, `swipe`, `assertVisible`, `assertNotVisible`, `assert`, `uiTree`, and `assertWithAI`. The Android action catalog may describe `perform_actions` / `performActions`, but an unimplemented uiautomator2 backend method must not be decorated as a capability and must not appear in harness `action_space()` or SDK tool exposure.

Capability metadata, not a static Android action table, is the runtime source of truth for Android method name, parameter model, step kind, owner, platform/backend metadata, replay alias, and evidence capture intent. Android action catalog entries are declaration-time validation inputs that generate capability metadata; they are not an execution path or parser fallback.

## Internal Structure

- `__init__.py`: Public exports only.
- `_capabilities.py`: Capability registry, alias resolution, duplicate validation, executor bindings, and snapshot creation.
- `_default_capabilities.py`: Android harness/driver capability definitions used by entry-layer registry bootstrap without constructing a real backend connection.
- `runner/__init__.py`: Runner subpackage exports only.
- `runner/_runner.py`: `StepRunner` implementation for single-step capability execution.
- `runner/_sequence.py`: `StepSequenceRunner` implementation for ordered execution and evidence recording.
- `harness/__init__.py`: Harness subpackage exports only.
- `harness/_interface.py`: `HarnessInterface` and `AIAssertionEvaluatorProtocol` protocols.
- `harness/_android.py`: Built-in `AndroidHarness` implementation and Android harness-owned capability declarations.
- `harness/_android_driver.py`: `AndroidDriverInterface` protocol and driver-owned contracts.
- `harness/_driver_tools.py`: Thin driver declaration compatibility helpers, Android action catalog wiring, and function schema/capability discovery wrappers backed by `capabilities`.
- `harness/_uiautomator2_driver.py`: Optional uiautomator2 backend implementation with lazy dependency import and fake-device injection for tests.
- `evidence/__init__.py`: Evidence subpackage exports only.
- `evidence/_recorder.py`: `EvidenceRecorder` implementation.
- `evidence/_artifact_store.py`: `ArtifactStore` implementation for run-local artifact paths and file writing.
- `SPEC.md`: Module design.

Core must not define Pydantic models shared across modules. Shared models belong in `fsq_agent.models`.

## Python Architecture

- Architecture level: 3 Layered Application.
- Public API: capability registry, executor bindings, Android capability definitions, runner, sequence runner, harness protocols, Android harness/driver contracts, evidence recorder/store, and provider-neutral AI assertion evaluator protocol exported from package/subpackage `__init__.py` files.
- Internal modules: all `_*.py` files and implementation subpackages remain private outside documented exports.
- Domain boundaries: core owns execution orchestration and provider-neutral platform coordination. Provider construction, SDK tool creation, CLI parsing, FSQ parsing, and report generation live outside core.
- Boundary models: all serializable contracts come from `models`; core protocols and concrete runners operate on those contracts.
- Dependency direction: core imports `models` and `capabilities` only among project modules. Entry modules inject tool executors, providers, concrete harnesses, and settings.
- Rationale: execution routing coordinates multiple side-effecting components and evidence flow, so Level 3 is warranted; no persistence/domain complexity justifies Clean Architecture or DDD.

## Error Handling

Registry bootstrap failures are configuration errors and must occur before YAML parsing or SDK tool exposure. Duplicate names, ambiguous aliases, ambiguous replay aliases, missing parameter models, missing executor bindings, unsupported executor kinds, invalid sensitivity result shapes, and eager backend connections during registry build fail fast.

Runner phases preserve failure boundaries:

- prepare failures: registry lookup, context, setup, validation, or before-action observation failures
- invoke failures: action, target, timeout, platform command, CommonTool, provider-backed assertion, or backend failures
- finalize failures: after-action observation, artifact capture, stabilization, cleanup, or event persistence failures

Harness action payload validation errors are configuration failures and must be returned as structured failed results before any backend side effect. Driver target misses, assertion failures, action errors, artifact errors, and backend exceptions become structured runner results. Strict mode rejects silent recovery; target misses remain failures unless a future recovery mode runs separately with separate evidence.

Sensitive capabilities must return values in the standard normalized shape `output.value`. Persisted events, manifests, reports, artifacts, previews, and historical tool-output trimming must redact or omit sensitive values. A sensitive capability result that does not use the standard shape fails as a capability implementation/configuration error and raw output must not be persisted.

## Testing Contract

- Unit tests: registry validation, alias resolution, duplicate/ambiguous failures, StepRunner routing by executor kind, capability-derived evidence policy application, explicit evidence policy preservation, sensitivity redaction, structured event payloads, sequence teardown behavior, and Android harness dispatch.
- Integration-style tests with fakes: strict `waitMs` alias resolves to canonical `wait_ms`; dynamic and strict `wait_ms` reach the same decorated implementation; Android aliases resolve to canonical driver capabilities; registry bootstrap does not connect to real Android devices.
- Regression tests: no `waitMs` action-name special branch in StepRunner, no static Android action registry dependency in FSQ parsing, no name-based CommonTool replay/sensitivity branches, and no dynamic/strict drift for `capture_evidence=True` harness or driver capabilities.
- Verification commands: `./.venv/Scripts/python.exe -m pytest tests/test_core_contracts.py tests/test_step_runner.py tests/test_android_harness.py` plus broader tests when implementation touches CLI/agent/report paths.

## Design Decisions

- Decorator metadata produced through the shared `capabilities` declaration layer is the source of truth for executable capabilities. Android action catalog entries validate declarations and prevent platform drift, but static Android action tables, separate harness schemas, and separate CommonTool definitions are not runtime authorities in the target architecture.
- `StepRunner` owns execution control, metadata-driven routing, evidence policy application, result normalization, sensitivity handling, and structured event emission.
- CommonTools are execution capabilities routed by `executor_kind="common"`; they are not a separate dynamic-only tool path.
- `wait_ms` is a decorated CommonTool capability with replay alias `waitMs`, not a core-owned special command.
- `get_runtime_secret` is a decorated sensitive CommonTool capability with dependency replay alias `runtimeSecret`, not a report/recorder special case.
- Harness-owned actions such as Android `assert_with_ai` use the same capability metadata path as driver-backed actions but route through the active harness rather than a driver method.
- Concrete drivers control dynamic exposure by decorating implemented methods with shared capability metadata. A protocol method existing on `AndroidDriverInterface`, a Pydantic parameter model, or an action catalog entry is not enough to expose it to the registry or to the LLM. Future web, desktop, and iOS platforms should add platform action catalogs and reuse catalog-backed declaration helpers rather than creating platform-specific decorator implementations.
- Android backend construction must be lazy enough that registry bootstrap and strict YAML parsing never require a real device connection.
- AI assertion is explicit assertion execution. It may call an injected evaluator only because the authored capability requested AI assertion; it must not be used for locator fallback, action repair, screenshot reinspection of unrelated steps, or testcase mutation.
- Locator self-healing is not part of strict execution. Any deterministic fallback or AI-assisted repair must be represented as recovery execution so reports can compare strict truth with recovery outcome.
- Evidence artifacts use run-relative paths. `ArtifactStore` owns directory layout and artifact writing; runners and harnesses do not construct artifact paths manually.