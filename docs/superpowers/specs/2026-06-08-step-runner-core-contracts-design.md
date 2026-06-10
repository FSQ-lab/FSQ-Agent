# Step Runner Core Contracts Design Spec

Status: draft for project-guide review
Date: 2026-06-08
Scope: first implementation batch for FSQ-Agent execution-core contracts under the project module rules
Language policy: English is the contract source of truth. Chinese notes are included where they clarify team intent.

## 1. Purpose

This spec defines the first implementation batch for the FSQ-Agent StepRunner architecture. The goal is to establish stable contracts before connecting real platform execution, CLI entry points, reports, or verifiers.

The target architecture follows the pytest-style execution protocol described in `docs/step-runner-architecture.md`:

```text
Planner output / FSQ step
  -> StepBuilder
  -> ExecutableStep
  -> StepRunner
  -> HarnessInterface
  -> RunnerEvents
  -> EvidenceRecorder
  -> EvidenceBundle
```

For this first batch, the work intentionally focuses on contracts and project-spec alignment:

```text
models-owned ExecutableStep and runner protocol models
core-owned HarnessInterface protocol boundary
models-owned RunnerEvent models
models-owned EvidenceBundle manifest schema
core module SPEC and DAG registration
```

It does not implement real Android/Web/iOS harness behavior, CLI integration, report generation, verifier integration, or planner repair.

中文摘要：第一批先把 Runner、Harness、Evidence 的稳定契约立住，不急着接真实设备、CLI、report/verifier。这样后续团队分工时不会把执行控制、平台能力和证据记录混在一起。

## 2. Confirmed Decisions

- Create a new root package: `fsq_agent/core/`, but only after adding `fsq_agent/core/SPEC.md` and registering the module in `CLAUDE.md`.
- Split execution-core modules under that root:
  - `fsq_agent/core/runner/`
  - `fsq_agent/core/harness/`
  - `fsq_agent/core/evidence/`
- Place `ExecutableStep` and other shared Pydantic data contracts in `fsq_agent.models`, not in `fsq_agent.core`, because `CLAUDE.md` requires shared data structures to live only in `models`.
- Let `fsq_agent/core/runner/` consume `ExecutableStep` from `models` as the direct input contract for future `StepRunner` work.
- Use Pydantic `BaseModel` for structured data contracts in `models`.
- Use `typing.Protocol` for `HarnessInterface` because it is a capability interface, not a persisted data model.
- Keep the first batch contract-first and test-first. Product integration comes later.

## 3. Approaches Considered

### Approach A: Minimal Vertical Slice

Implement `ExecutableStep -> StepRunner -> FakeHarness -> RunnerEvents -> EvidenceRecorder` with one successful and one failed `tap` step.

Trade-off: This validates behavior quickly, but it can force contracts to evolve while implementation pressure is already present. It is useful after the contracts are stable.

### Approach B: Stable Contracts First

Define the shared Pydantic models in `models`, the `HarnessInterface` protocol in `core`, the event taxonomy, and evidence manifest schema before wiring execution flows.

Trade-off: This produces less visible runtime behavior in the first batch, but it gives the team a stable boundary for parallel work. This is the selected approach.

### Approach C: Direct FSQ Flow Integration

Connect existing `FsqCase` / `FsqTaskAdapter` paths into the new runner pipeline immediately.

Trade-off: This gives end-to-end value sooner, but it risks coupling the new core contracts to legacy `Task` / `StepResult` assumptions before the pytest-style phase model is settled.

Recommendation: Use Approach B first, then implement Approach A as the second batch, then Approach C after the core event and evidence contracts have working tests.

## 4. Package Layout

The first batch should introduce or prepare this structure:

```text
fsq_agent/core/
  __init__.py
  SPEC.md
  runner/
    __init__.py
    _runner.py
  harness/
    __init__.py
    _interface.py
  evidence/
    __init__.py
    _recorder.py
fsq_agent/models/
  _core.py
```

The module split is intentionally small. `StepRunner` implementation can be added in a later batch as `fsq_agent/core/runner/_runner.py` after the models are tested. Shared Pydantic contracts should be added in `fsq_agent/models/_core.py` and exported through `fsq_agent/models/__init__.py`.

Public exports should be explicit through each module's `__init__.py`. Internal files should keep leading underscores, matching existing repository style.

## 5. Modeling Policy

Use Pydantic for data contracts because the repository already uses Pydantic for core models such as `FsqCase`, `Task`, `StepResult`, and verification models. Per `CLAUDE.md`, these shared contracts belong in `fsq_agent.models`.

Pydantic should be used for:

- `ExecutableStep`
- `SourceRef`
- `RetryPolicy`
- `EvidencePolicy`
- `StepCallInfo`
- `StepPhaseReport`
- distinct execution-core step result model name to be confirmed before implementation
- `RunnerEvent`
- `HarnessContext`
- `HarnessActionResult`
- `HarnessArtifactRef`
- `EvidenceBundle`
- `EvidenceManifest`

`Protocol` should be used in `fsq_agent.core.harness` for:

- `HarnessInterface`

Reasoning:

- Pydantic gives validation, serialization, manifest compatibility, and API readiness.
- `Protocol` lets `AndroidHarness`, `WebHarness`, `IOSHarness`, and `FakeHarness` satisfy the same contract without inheritance coupling.
- This keeps the key separation clear: shared data is modeled in `models`, capability is abstracted in `core`.

## 6. Runner Contracts

### 6.1 ExecutableStep

`ExecutableStep` is the direct input to the runner. It is produced by future `StepBuilder` work and consumed by future `StepRunner` work. The model is owned by `fsq_agent.models`, while `fsq_agent.core.runner` consumes it.

Minimum fields:

```text
step_id
source_ref
kind
action_name
params
target_ref
retry_policy
evidence_policy
timeout_ms
metadata
```

Guidance:

- `step_id` must be stable within one run.
- `source_ref` should trace back to YAML, planner output, or generated runtime step source.
- `kind` should distinguish action, assertion, observation, diagnostic, setup, and teardown intent.
- `params` should stay structured and JSON-serializable.
- `target_ref` should be optional because some actions do not require a target.
- `retry_policy`, `evidence_policy`, and `timeout_ms` are attached before runner execution.

### 6.2 Phase Protocol

The runner protocol should model each executable step as three phases:

```text
prepare
invoke
finalize
```

`prepare` owns context setup and before-action observation.
`invoke` owns the harness action call.
`finalize` owns after-action observation and phase outcome consolidation.

This mirrors pytest's `setup`, `call`, and `teardown` structure without copying pytest implementation details.

### 6.3 StepCallInfo

`StepCallInfo` is the structured wrapper for one phase call. Exceptions should be captured here before they become phase reports.

Minimum fields:

```text
phase
started_at
ended_at
duration_ms
status
return_value
exception_type
exception_message
failure_category
```

The runner should not let unstructured exceptions leak into reports or evidence. Every phase must either produce a successful call info or a failed call info.

### 6.4 StepPhaseReport

`StepPhaseReport` is the reportable result of one phase.

Minimum fields:

```text
step_id
phase
status
duration_ms
failure_category
error_message
artifact_refs
harness_call_refs
```

Phase reports make it possible to distinguish:

- prepare failure: context, device, setup, before-action observation, or step validation problem
- invoke failure: action, target, timeout, platform command, or assertion problem
- finalize failure: after-action observation, evidence capture, page stabilization, or cleanup problem

### 6.5 StepResult

The new execution-core step result should summarize the complete execution result of one `ExecutableStep`.

Minimum fields:

```text
step_id
source_ref
status
started_at
ended_at
duration_ms
phase_reports
attempt_index
max_attempts
failure_category
error_message
evidence_refs
metadata
```

This contract must avoid ambiguity with the existing `fsq_agent.models.StepResult`. Before implementation, choose a distinct public name such as `CoreStepResult`, `RunnerStepResult`, or `ExecutionStepResult`, then document it in `fsq_agent/models/SPEC.md` and export it from `fsq_agent.models`.

## 7. Runner Events

The runner should emit structured events. Evidence recording, terminal progress, report generation, debugging, and future live playgrounds should consume events rather than being imported directly by the runner.

First-batch event names:

```text
session_start
session_finish
step_start
phase_start
harness_call_start
harness_call_finish
artifact_captured
phase_finish
step_error
step_finish
```

Minimum event fields:

```text
event_id
event_type
run_id
step_id
phase
timestamp
payload
```

Design rule:

```text
StepRunner owns control.
Harness owns capability.
Evidence owns history.
```

The runner may emit events and return results. It should not write the final evidence manifest directly.

## 8. Harness Contracts

### 8.1 HarnessInterface

`HarnessInterface` is the stable platform capability contract. It should be defined as a `typing.Protocol` in `fsq_agent.core.harness` and use models-owned input/output contracts.

First-batch methods:

```text
get_context()
action_space()
before_action(step, context)
invoke_action(step, context)
after_action(step, context, action_result)
capture_artifact(kind, reason, context)
classify_error(error, phase, step)
```

The exact Python signatures should use typed Pydantic input/output models from `fsq_agent.models`.

### 8.2 HarnessContext

`HarnessContext` represents the current platform state available to the runner and harness methods.

Minimum fields:

```text
platform
session_id
capabilities
current_url
current_activity
screen_size
metadata
```

Fields must be optional where platform-specific. Web may provide `current_url`; Android may provide `current_activity`; both should fit the same model.

### 8.3 HarnessActionResult

`HarnessActionResult` represents a platform action outcome.

Minimum fields:

```text
status
action_name
started_at
ended_at
duration_ms
output
artifact_refs
error_message
failure_category
metadata
```

Harness implementations should report capability and platform facts. They should not decide case pass/fail.

### 8.4 Android Harness And Driver Extension Model

`HarnessInterface` is the runner-facing platform harness contract. It is higher-level than a raw device/page primitive interface. For Android, the preferred long-term product shape is:

```text
StepRunner
  -> HarnessInterface
      -> AndroidHarness          # FSQ built-in
          -> AndroidDriverInterface
              -> AppiumDriver
              -> UiAutomator2Driver
              -> UserCustomDriver
```

`AndroidHarness` should be built into FSQ and should implement `HarnessInterface`. It owns FSQ-specific execution semantics: mapping `ExecutableStep.action_name` to Android operations, producing `HarnessActionResult`, shaping `HarnessContext`, creating artifact refs, applying evidence policy entry points, and classifying Android/platform failures into shared `FailureCategory` values.

Users who want to use a different Android automation backend should usually implement `AndroidDriverInterface`, not a full custom `HarnessInterface`. The driver interface should expose lower-level Android primitives such as tap/click, input text, screenshot, UI tree capture, back, scroll, wait/stabilize, and backend-specific error details. This layer is closer to Midscene's low-level interface concept; `HarnessInterface` remains the higher-level contract seen by `StepRunner`.

Direct custom `HarnessInterface` implementations should remain possible for advanced platform plugins or non-Android platforms, but they should not be the ordinary Android backend extension path.

## 9. Evidence Contracts

### 9.1 EvidenceBundle

`EvidenceBundle` is the stable historical record for one run. It should be manifest-oriented and reference artifacts by path or URI-like internal refs rather than embedding binary data.

Minimum fields:

```text
bundle_id
run_id
created_at
schema_version
manifest_path
events
steps
artifacts
metadata
```

### 9.2 Evidence Manifest

The first implementation should prefer a single manifest model with typed artifact references. A directory-level bundle can be added later without changing the event or step contracts.

Minimum artifact ref fields:

```text
artifact_id
kind
path
mime_type
created_at
step_id
phase
metadata
```

Supported first-batch artifact kinds:

```text
screenshot
ui_tree
tool_call
log
json
text
other
```

### 9.3 EvidenceRecorder Boundary

The first batch may define models required by `EvidenceRecorder`, but should not implement a full writer unless needed for contract tests.

EvidenceRecorder should eventually:

- consume `RunnerEvent` values
- collect `StepPhaseReport` and `StepResult` facts
- assign artifact refs
- write `EvidenceBundle` manifest data

It should not execute actions, retry steps, or classify case success.

## 10. Error and Status Taxonomy

The first batch should define small, stable literal enums rather than broad free-form strings.

Recommended status values:

```text
pending
running
passed
failed
skipped
cancelled
```

Recommended phase values:

```text
prepare
invoke
finalize
```

Recommended failure categories:

```text
configuration_error
context_error
target_resolution_error
action_error
assertion_error
timeout_error
observation_error
artifact_error
harness_error
cancelled
unknown
```

The taxonomy can grow later, but the first batch should avoid platform-specific category names in core contracts.

## 11. Testing Strategy

Contract tests should verify model validation and boundary behavior without requiring real devices or network services.

Recommended tests:

- `ExecutableStep` accepts valid minimal and full payloads.
- `ExecutableStep` rejects invalid `kind`, phase, status, or non-serializable policy payloads where applicable.
- `HarnessInterface` can be satisfied by a small in-test fake class.
- `RunnerEvent` validates required fields and known event names.
- `StepPhaseReport` preserves prepare/invoke/finalize distinctions.
- `EvidenceBundle` serializes to JSON with artifact references and no binary payloads.
- Public exports from `fsq_agent.core.runner`, `fsq_agent.core.harness`, and `fsq_agent.core.evidence` are stable.

The first batch should not require Android, Appium, Playwright, OpenAI APIs, MCP startup, or CLI execution.

## 12. Implementation Batches

### Batch 1: Contracts

Update `CLAUDE.md`, add `fsq_agent/core/SPEC.md`, update `fsq_agent/models/SPEC.md`, then define Pydantic models/enums/literals in `fsq_agent.models`, the `HarnessInterface` protocol in `fsq_agent.core.harness`, and focused unit tests.

Expected outcome: stable importable contracts with passing tests and module boundaries that follow the project DAG.

### Batch 2: Minimal Runner Slice

Add `StepRunner`, in-test or module-level `FakeHarness`, deterministic event emission, and one success/failure flow through `prepare -> invoke -> finalize`.

Expected outcome: a `tap`-like `ExecutableStep` can run through FakeHarness and produce `StepResult` plus runner events.

### Batch 3: Evidence Recorder

Implement `EvidenceRecorder` and a manifest writer that consumes runner events and step reports.

Expected outcome: a run produces an `EvidenceBundle` manifest with step facts and artifact refs.

### Batch 4: Android Harness / Driver Contracts

Define the built-in `AndroidHarness` contract boundary and the lower-level `AndroidDriverInterface` extension point. Use in-test fake drivers to validate action dispatch for a small operation set such as `tap`, `inputText`, `back`, screenshot, and UI tree capture. Do not require real Appium or uiautomator2 in this batch.

Expected outcome: Android backend authors have a smaller driver interface to implement, while `StepRunner` continues to depend only on `HarnessInterface`.

### Batch 5: FSQ Integration

Adapt existing FSQ paths so YAML/planner steps can become `ExecutableStep[]` through StepBuilder work.

Expected outcome: FSQ regression path starts converging on the shared execution core.

### Batch 6: Report and Verifier Integration

Add adapters so report and verifier code can read from `EvidenceBundle` rather than relying only on legacy `StepResult` summaries or agent claims.

Expected outcome: reports and verification consume historical facts from the new core evidence system.

## 13. Out of Scope for Batch 1

- Real Android harness implementation.
- Real Web harness implementation.
- Appium, Playwright, MCP, or device lifecycle integration.
- CLI command changes.
- Report generator changes.
- Verifier prompt or verifier model changes.
- Planner repair policy.
- Retry execution behavior beyond modeling `RetryPolicy`.
- Backward compatibility adapters for existing `fsq_agent.models.StepResult`.
- Defining shared Pydantic data models inside `fsq_agent.core`.

## 14. Open Follow-Up Decisions

These decisions should be made during later batches, not before Batch 1:

- Whether `StepRunner` should be sync-only first or support async harness methods.
- Whether `EvidenceRecorder` writes a single manifest file or a directory-level bundle with multiple typed manifests.
- Whether `FakeHarness` belongs under `core/harness/` or only under tests.
- What distinct public name should be used for the new execution-core step result so it does not conflict with legacy `fsq_agent.models.StepResult`.
- How legacy `fsq_agent.models.StepResult` maps to the new execution-core step result.
- Where StepBuilder should live once Owner 1 contracts are moved or expanded.

## 15. Acceptance Criteria

This design is ready for implementation planning after user review confirms:

- The team agrees that Batch 1 is contract-only.
- `fsq_agent/core/runner/`, `fsq_agent/core/harness/`, and `fsq_agent/core/evidence/` are accepted as package boundaries.
- `ExecutableStep` and other shared data contracts are accepted as `models`-owned contracts consumed by `core/runner/`.
- Pydantic-in-`models` for data and Protocol-in-`core` for harness is accepted as the modeling rule.
- Later runtime behavior is explicitly deferred to Batch 2 and beyond.
