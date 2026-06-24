# Strict Capture Evidence Parity Design

## Goal

Fix the inconsistency where Android capabilities declared with `capture_evidence=True` receive the standard before/after evidence policy during dynamic LLM execution, but do not receive the same policy during strict FSQ replay.

Strict replay and dynamic execution must use the same capability metadata semantics for `capture_evidence`. The implementation must avoid copying policy construction logic into both dynamic and strict adapters.

## Scope

This design covers the execution-policy path for `CapabilityDefinition.capture_evidence` across dynamic and strict execution:

- Dynamic harness tool calls created by the agent runtime.
- Strict FSQ replay steps created by `FsqExecutableStepAdapter` and executed through CLI or playground strict paths.
- Core `StepRunner` behavior for harness and driver capabilities that are resolved through the capability registry.
- Tests and SPEC synchronization needed to prove the parity.

## Non-Goals

This design does not change these behaviors:

- It does not add user-authored FSQ evidence controls.
- It does not add config flags to enable or disable screenshots.
- It does not change replay policy, sensitivity policy, SDK strict-schema behavior, runtime secret resolution, or dynamic recording semantics except where tests need metadata to stay aligned.
- It does not expose unimplemented Android `performActions`.
- It does not change `assertWithAI`'s harness-owned screenshot capture for AI evaluation.
- It does not redesign reports beyond preserving the evidence artifacts already produced by runner phase reports.

## Resolved Questions

- Strict replay should completely match the current dynamic behavior for capabilities with `capture_evidence=True`: capture before, after, and on failure; artifact kinds are `screenshot` and `ui_tree`.
- The policy must not be copied into both dynamic and strict paths. A shared execution-layer decision is preferred for maintainability.

## Approaches Considered

### A. Set Evidence Policy In `fsq`

`FsqExecutableStepAdapter` could inspect `capability.capture_evidence` and set the same `EvidencePolicy` that dynamic currently sets.

Pros:

- Small local change for strict replay.
- Keeps `StepRunner` behavior nearly unchanged.

Cons:

- Duplicates dynamic adapter logic in `fsq`.
- Makes `fsq` responsible for an execution policy, even though it is intended to parse and normalize deterministic steps only.
- Future changes to the standard evidence policy would need edits in multiple modules.

### B. Derive Effective Evidence Policy In `core` (Recommended)

`StepRunner` already resolves each `ExecutableStep` through `CapabilityRegistry`. It should derive an effective evidence policy from the resolved `CapabilityDefinition` and the step's policy before executing harness or driver phases.

Pros:

- Matches the root and core SPEC direction: capability metadata is the execution contract and `StepRunner` applies evidence policy.
- Dynamic and strict paths both converge at `StepRunner.run_step`, so one implementation serves both.
- Keeps `fsq` focused on YAML-to-step conversion and keeps `agent` focused on SDK adaptation.
- Avoids action-name allowlists and avoids duplicating policy construction.

Cons:

- Requires careful merge rules so existing explicit `ExecutableStep.evidence_policy` tests keep working.
- Requires dynamic adapter tests to be updated because the adapter should no longer be the owner of the standard evidence policy conversion.

### C. Put A Shared Helper In `models`

The standard policy helper could live with `EvidencePolicy` in `models` and be called by both adapters.

Pros:

- Avoids direct code duplication between dynamic and strict adapters.

Cons:

- Adds behavior to `models`, whose SPEC says it owns contracts and validation only.
- Still requires both adapters to remember to call the helper.
- Does not align as well with the existing `StepRunner` execution responsibility.

## Recommended Design

Use Approach B: centralize `capture_evidence` execution semantics in `core.StepRunner`.

`StepRunner` should compute an effective evidence policy after resolving the capability and before entering the prepare/invoke/finalize path for harness and driver capabilities.

The standard policy for a resolved harness or driver capability with `capture_evidence=True` is:

- `capture_before=True`
- `capture_after=True`
- `capture_on_failure=True`
- `artifact_kinds=["screenshot", "ui_tree"]`

Capabilities with `capture_evidence=False` keep the normal default behavior unless the `ExecutableStep` already carries a non-default evidence policy.

Explicit step-level policies should remain supported. A step policy that differs from the shared default `EvidencePolicy()` should be treated as explicit and should not be overwritten by capability metadata. This preserves targeted tests and future entry-layer callers that intentionally supply custom artifact kinds or capture phases. A default step policy should allow the resolved capability metadata to provide the standard evidence behavior.

## Architecture And Module Ownership

### `core`

`core` owns the effective policy derivation because it owns `StepRunner`, capability registry resolution, harness execution phases, and artifact capture coordination.

Expected responsibilities:

- Resolve capability metadata through `CapabilityRegistry` once per step.
- Build the effective evidence policy from capability metadata plus any explicit step policy.
- Use the effective policy for prepare and finalize artifact capture.
- Keep artifact capture implementation in the existing runner/harness path.
- Avoid action-name branches such as checking `tap_on`, `input_text`, or `launch_app`.

### `agent`

`agent` should continue adapting harness schemas into SDK tools and constructing canonical `ExecutableStep` values. It should stop owning the standard `capture_evidence=True` to `EvidencePolicy` conversion for harness tools.

Dynamic execution remains behaviorally unchanged because all dynamic harness tool calls still execute through `StepRunner` with a capability registry.

### `fsq`

`fsq` should continue converting parsed `.codex.yaml` commands into canonical `ExecutableStep` records using `CapabilityRegistrySnapshot`. It should not import `core`, call runtime helpers, or duplicate the standard evidence policy.

The step adapter may preserve default `EvidencePolicy()` on produced steps. The effective policy is an execution concern handled by `StepRunner`.

### `cli` And `playground`

Strict CLI and playground flows already route parsed strict steps through `StepSequenceRunner` and `StepRunner`. They should not need separate evidence-policy logic. Their SPECs and tests should verify that strict runs now produce the same evidence artifacts for `capture_evidence=True` capabilities.

### `models`

No new model type is required. `EvidencePolicy` and `CapabilityDefinition.capture_evidence` remain the shared contracts.

The models SPEC should be synchronized so `capture_evidence` is no longer described as dynamic-only behavior.

## Python Architecture Level

The affected architecture stays at the existing levels:

- `core`: Level 3 Layered Application, because it coordinates capability execution, harness interaction, and evidence flow.
- `agent` and `cli`: Level 3 Layered Application, because they orchestrate runtime and entry workflows but should delegate execution policy to `core`.
- `fsq`, `models`, and `tools`: Level 2 Simple Package, because their responsibilities remain focused on contracts, parsing, and utility capability hosting.

No new package or public abstraction is justified. The simplest viable design is a private core helper or private `StepRunner` method that computes the effective policy from existing models.

## Public Behavior

After the change, a strict `.codex.yaml` command such as `tapOn`, `inputText`, `pressKey`, `swipe`, `launchApp`, `killApp`, or `longPressOn` should produce the same runner artifact behavior as the equivalent dynamic harness tool call:

- prepare phase captures `screenshot` and `ui_tree` with reason `before-action`;
- finalize phase captures `screenshot` and `ui_tree` with reason `after-action`;
- failed/cancelled/skipped results additionally capture `screenshot` and `ui_tree` with reason `failure`;
- captured artifacts appear in phase reports, runner artifact events, evidence manifests, and strict core reports through the existing artifact pipeline.

Capabilities that do not declare `capture_evidence=True`, such as `assert_visible`, `assert_not_visible`, `assert_state`, `assert_with_ai`, and `ui_tree`, should not receive automatic before/after screenshot and UI tree artifacts. `assert_with_ai` may still capture its own invocation screenshot for AI evaluation as it does today.

## Data And Control Flow

Dynamic flow after the design:

1. `AndroidHarness.action_space()` exposes schemas generated from capability definitions.
2. `HarnessToolAdapter` builds SDK tools and creates canonical `ExecutableStep` values with default step evidence policy.
3. `StepRunner.run_step()` resolves the capability, derives the effective evidence policy, and executes prepare/invoke/finalize phases.
4. Artifact refs and events are returned to the dynamic adapter through the existing `RunnerStepResult` path.

Strict flow after the design:

1. CLI or playground builds the capability registry.
2. `FsqExecutableStepAdapter` resolves authored FSQ aliases, validates params, and creates canonical `ExecutableStep` values with default step evidence policy.
3. Strict replay reference resolution updates only step params.
4. `StepSequenceRunner` calls `StepRunner.run_step()` for each step.
5. `StepRunner` derives the same effective evidence policy and captures the same artifacts as dynamic execution.

## Error Handling And Edge Cases

- Artifact capture failures should continue to be reported as `artifact_error` in the affected phase and should fail the step using current runner behavior.
- If the harness lacks support for an artifact kind listed in the effective policy, that remains an artifact capture failure. AndroidHarness already supports `screenshot` and `ui_tree`.
- Explicit non-default `ExecutableStep.evidence_policy` should be respected so tests and future callers can narrow or customize capture behavior.
- Default `EvidencePolicy()` should not suppress capability metadata. This is the core fix for strict replay.
- CommonTool capabilities are not part of the standard screenshot/UI tree policy in this design because current `capture_evidence=True` use is for platform harness/driver capabilities. Future CommonTool evidence behavior should get its own SPEC update if needed.
- `timeout_ms` extraction and runtime-secret resolution remain strict-entry concerns and are not changed by evidence policy derivation.

## Affected Specs Expected To Change

The implementation phase should update these specs before code changes:

- Root `SPEC.md`: confirm `capture_evidence` behavior is shared across dynamic and strict, if wording needs tightening.
- `fsq_agent/core/SPEC.md`: make effective evidence policy derivation explicit and describe the merge rule between capability metadata and explicit step policy.
- `fsq_agent/agent/SPEC.md`: move ownership of standard evidence policy conversion from the dynamic adapter to `StepRunner`.
- `fsq_agent/fsq/SPEC.md`: replace the current "default shared model policy for now" wording with "default step policy; effective execution policy is derived by core".
- `fsq_agent/models/SPEC.md`: remove dynamic-only wording for `capture_evidence` and state it is a shared execution metadata contract.
- `fsq_agent/cli/SPEC.md`: note that strict runs now receive capability-derived evidence artifacts through the shared core path.
- `fsq_agent/playground/SPEC.md`, if it currently describes strict YAML evidence behavior separately.

## Verification Expectations

Focused tests should cover:

- `StepRunner` derives the standard screenshot/UI tree policy for a registered harness or driver capability with `capture_evidence=True` when the step carries the default policy.
- `StepRunner` does not derive artifacts for `capture_evidence=False` capabilities.
- Explicit non-default step evidence policy is preserved and not overwritten by capability metadata.
- Dynamic harness tool calls still capture the same before/after artifacts as before.
- Strict FSQ replay through `run_fsq_core_case` captures before/after artifacts for mutating Android commands such as `tapOn` using fake harnesses.
- Strict failures capture the failure artifacts when `capture_evidence=True`.
- Assertions and read-only observation commands remain free of automatic before/after evidence unless they explicitly return invocation artifacts.

Recommended commands for the implementation phase:

```text
.\.venv\Scripts\python.exe -m pytest tests/test_step_runner.py tests/test_fsq_executable_step_adapter.py tests/test_cli_core_execution.py tests/test_openai_runtime.py tests/test_android_harness.py tests/test_capabilities.py
```

Broader verification is appropriate if SPEC changes touch report, playground, or CLI behavior beyond evidence artifact propagation.

## Audit Expectations

The post-implementation audit should check:

- No duplicated standard evidence policy construction remains in both dynamic and strict adapters.
- No Android action-name allowlist is introduced into `StepRunner`.
- `fsq` still imports only `models` among project modules.
- `models` remains contract-only and does not gain execution helper behavior.
- Strict and dynamic evidence manifests contain equivalent artifact kinds and phase reasons for the same `capture_evidence=True` capability.
- Existing AI assertion screenshot behavior remains invocation-owned and separate from before/after evidence policy.