# Capability Post-Action Delay Design

Date: 2026-06-24
Status: Confirmed design for SPEC review

## Goal

Redefine the current step interval behavior from strict-only sequencing delay into a capability-owned post-action stabilization delay that applies consistently to dynamic and strict execution.

The user-visible problem is that a platform action can return while the app UI is still transitioning. If the runner immediately captures after-action evidence, the screenshot or UI tree may represent an intermediate state. If strict replay immediately executes the next platform action, the target may not yet be ready. The delay must therefore happen after the capability invoke phase and before after-action/failure evidence capture or the next executable action.

## Scope

This design covers execution pacing for capabilities routed through `StepRunner`:

- dynamic LLM harness and CommonTool execution,
- strict-core YAML execution,
- playground strict execution,
- harness-owned capabilities,
- driver/platform capabilities,
- CommonTool capabilities.

The design changes the meaning and scope of the existing `step_interval_seconds` concept, but it does not implement code and does not update `SPEC.md` files.

## Non-Goals

Do not add synthetic `waitMs` commands to parsed FSQ cases, generated strict recordings, evidence manifests, or reports.

Do not keep strict-only step-between sleep as the authoritative pacing behavior.

Do not make CommonTools wait by default. CommonTools default to no post-action delay unless their capability declaration explicitly overrides that default or configuration later chooses a nonzero common default.

Do not use action-name allowlists in `StepRunner`. Delay behavior must come from capability metadata plus configuration defaults.

Do not use `before_action` or `after_action` hooks to implement generic screenshots or generic stabilization delay. Those hooks remain harness extension points.

## Confirmed Decisions

- Use `execution.post_action_delay_seconds` as the new YAML configuration surface.
- Split configured defaults by capability domain:
  - platform default for `harness` and `driver` capabilities,
  - common default for `common` capabilities.
- Default platform post-action delay is `1.0` seconds.
- Default common post-action delay is `0.0` seconds.
- Add an explicit typed capability/decorator override field instead of burying this behavior in opaque metadata.
- Decorator override semantics are:
  - `None`: use the configured default for the capability executor kind,
  - `0`: explicitly disable post-action delay for this capability,
  - positive value: use this capability-specific delay in seconds.

## Proposed Configuration

Preferred YAML shape:

```yaml
execution:
  post_action_delay_seconds:
    platform: 1.0
    common: 0.0
```

`platform` applies to `executor_kind="harness"` and `executor_kind="driver"` when a capability does not declare an override.

`common` applies to `executor_kind="common"` when a capability does not declare an override.

Both values must be non-negative floats. Zero means no implicit delay.

The old `harness.strict_core.step_interval_seconds` path should be removed from the preferred config shape because it is strict-specific in name and location, while the new behavior is `StepRunner`-owned and applies to dynamic and strict execution. The implementation may choose either an actionable validation error for the old key or a narrow one-cycle migration shim, but the confirmed target SPEC should describe only the new `execution.post_action_delay_seconds` contract.

## Capability Contract

Add a typed optional field to `CapabilityDefinition`, for example:

```text
post_action_delay_seconds: float | None = None
```

The field belongs in `models` because `CapabilityDefinition` is the shared serializable capability contract consumed by the registry, `StepRunner`, SDK adapters, strict parsing, reports, and recording. It must be included in safe capability metadata so reports and diagnostics can explain why a delay was or was not applied.

The shared decorator layer in `capabilities` should accept the same optional field on:

- `capability`,
- `common_capability`,
- `harness_capability`,
- `driver_capability`,
- `platform_driver_capability`.

`CapabilityActionDefinition` should also accept the field so platform catalogs can provide action-level defaults. A decorator argument should override the catalog value, matching the existing catalog-backed override pattern for evidence capture.

Validation must reject negative decorator/catalog values. `None` must remain distinct from `0`.

## Initial Capability Policy

The platform default should apply to harness and driver capabilities unless the declaration says otherwise. This keeps Android mutating actions such as `tap_on`, `input_text`, `press_key`, `swipe`, `launch_app`, `kill_app`, and `long_press_on` simple: they can inherit the configured platform delay.

Read-only or observation-style platform capabilities should explicitly override to `0` when a delay is not useful. Examples include `ui_tree` and any future diagnostic-only platform capability.

Assertion capabilities need an explicit implementation decision during SPEC update. The recommended default is:

- state-observing assertions that do not mutate UI may set `post_action_delay_seconds=0`,
- assertion capabilities that are expected to wait for app stabilization may inherit the platform default,
- provider-backed `assert_with_ai` should not add a second generic delay unless SPEC review decides its screenshot timing benefits from the shared delay.

CommonTools inherit the configured common default, which is `0.0`. `wait_ms` remains an explicit elapsed-time capability and should not receive an extra post-action delay unless deliberately declared later.

## Runner Behavior

`StepRunner` should resolve an effective post-action delay for every capability after registry resolution:

1. If `capability.post_action_delay_seconds` is not `None`, use that value.
2. Else if `capability.executor_kind` is `common`, use `execution.post_action_delay_seconds.common`.
3. Else if `capability.executor_kind` is `harness` or `driver`, use `execution.post_action_delay_seconds.platform`.
4. Else use `0` and treat unsupported executor kinds as existing configuration errors.

For harness and driver capabilities, the delay should occur after the invoke phase has completed or been converted into a structured invoke failure, and before finalize behavior begins. In current phase terms, the delay belongs between `invoke` and `finalize` so `after_action`, `capture_after`, and `capture_on_failure` observe the stabilized UI.

For CommonTool capabilities, the delay should occur after the common invoke phase and before the common finalize phase only when the effective delay is greater than zero. With the confirmed default, normal CommonTools do not wait.

The delay must not create an additional `ExecutableStep`, `waitMs` command, evidence step, replay command, or action result. It is execution timing only.

Runner result metadata should include enough safe information to audit pacing, for example the resolved delay seconds and whether it came from capability override or configuration default. A new runner event is optional; if added, it must be a safe execution-timing event and not an evidence artifact.

## Implementation Placement

The actual delay call, for example `time.sleep(delay_seconds)`, should live in `core` inside `StepRunner`, most likely in `fsq_agent/core/runner/_runner.py` as a small private helper such as `_apply_post_action_delay(...)` or `_sleep_after_invoke(...)`.

`StepRunner` is the right owner because it is the only shared execution point used by both dynamic tool calls and strict replay, and it already owns invoke/finalize phase ordering, evidence timing, event emission, and normalized results. Keeping the sleep there guarantees that the same delay happens before `after_action`, before `capture_after`, before `capture_on_failure`, and before the next strict step can begin.

The helper should receive already-resolved capability metadata and should not import `config`. Entry layers should translate loaded settings into a small runner-owned delay policy or primitive values when constructing `StepRunner`. This preserves the existing core dependency boundary: `core` may depend on shared `models`, but not on `config`, `agent`, `cli`, or `playground`.

The sleep should not be implemented in:

- `StepSequenceRunner`, because dynamic execution bypasses it and because strict evidence capture would still happen before the delay.
- `HarnessInterface.before_action` or `after_action`, because those are platform extension hooks and would hide shared runner timing inside harness implementations.
- Android driver methods, because that would duplicate policy across backends and would not apply to harness-owned capabilities.
- Config loading, because config should validate values, not execute runtime behavior.
- Capability decorators or discovery, because they declare metadata only and must remain side-effect free.

Tests should monkeypatch `fsq_agent.core.runner._runner.time.sleep` or inject a runner-local sleeper if implementation chooses an injectable helper. The first implementation should prefer the simplest private helper unless testing shows constructor injection is cleaner.

## Dynamic And Strict Flow

Dynamic execution already routes harness and CommonTool SDK calls through `StepRunner` by building canonical `ExecutableStep` values. The dynamic runtime should pass the configured post-action delay policy into the `StepRunner` instance used by `HarnessToolAdapter`. Because `AgentsCommonToolAdapter` delegates CommonTool execution through that runner invoker, dynamic harness tools and dynamic CommonTools share the same policy.

Strict execution should pass the same policy into the `StepRunner` used by `StepSequenceRunner`. `StepSequenceRunner` should stop owning the configured step interval. Its responsibility remains serial ordering, evidence recording, stop-on-failure behavior, and teardown execution.

Playground strict execution should use the same policy from loaded settings so browser-driven strict runs behave like CLI strict runs.

## Approaches Considered

### Approach A: Keep StepSequenceRunner Step-Between Sleep

This is the current behavior. It is cheap for strict replay, but it does not affect dynamic execution because dynamic calls use `StepRunner` directly. It also waits before the next step rather than before after-action evidence, so screenshots can still capture a transition state. This approach is rejected.

### Approach B: Executor-Kind Defaults Only

`StepRunner` could delay all harness/driver capabilities and skip all CommonTools based only on `executor_kind`.

This is simple and cheap, but it cannot express read-only platform actions, assertion differences, or future CommonTools that should wait. It is rejected because the project already has unified decorator metadata and the user confirmed decorator-controlled extensibility.

### Approach C: Capability Override Plus Configured Domain Defaults

`StepRunner` resolves delay from typed capability metadata first, then falls back to configured platform/common defaults.

This keeps runtime behavior metadata-driven, works for dynamic and strict paths, defaults platform actions to stable screenshots and safer next-step timing, and keeps CommonTools fast by default. This is the selected approach.

## Python Architecture

Architecture level: Level 3 Layered Application for the execution change, because the behavior coordinates config loading, shared capability metadata, dynamic SDK adapters, strict entry paths, and runner phase ordering.

Module-level changes remain at each module's existing level:

- `models`: Level 2 Simple Package. Owns the new serializable settings and capability contract fields.
- `capabilities`: Level 2 Simple Package. Owns declaration-time parameters and validation for the delay override.
- `config`: Level 2 Simple Package. Owns YAML loading and validation for `execution.post_action_delay_seconds`.
- `core`: Level 3 Layered Application. Owns `StepRunner` delay resolution and phase ordering.
- `agent`, `cli`, and `playground`: Level 3 Layered Application. Own passing the loaded policy into their `StepRunner` construction points.

No repository, Unit of Work, Clean Architecture, or DDD pattern is justified. The change is a small cross-cutting execution policy with existing boundary models and existing orchestration layers.

## Module Ownership

`models` should add shared configuration models such as `ExecutionSettings` and `PostActionDelaySettings`, and add `post_action_delay_seconds` to `CapabilityDefinition`.

`capabilities` should add the optional decorator/catalog argument, validate non-negative values, and include the field in discovered `CapabilityDefinition` records.

`config` should load and validate the new `execution.post_action_delay_seconds` YAML shape and remove the strict-only wording from config docs.

`core` should resolve and apply effective post-action delay in `StepRunner`. `StepSequenceRunner` should no longer implement the configured sleep between steps.

`agent` should pass execution delay settings into the dynamic `StepRunner` used by `HarnessToolAdapter`.

`cli` should pass execution delay settings into strict-core helper construction and update helper signatures away from `step_interval_seconds`.

`playground` should pass execution delay settings into its strict execution helper.

`tools` should not own the delay algorithm. CommonTool declarations may use the shared decorator override field when a CommonTool needs non-default delay behavior.

## Affected Specs Expected To Change

- `SPEC.md`: update decorated capability execution and runtime configuration defaults from strict-only pacing to capability post-action delay.
- `fsq_agent/models/SPEC.md`: add execution delay settings and `CapabilityDefinition.post_action_delay_seconds`.
- `fsq_agent/capabilities/SPEC.md`: add decorator/catalog delay override support.
- `fsq_agent/config/SPEC.md`: replace `harness.strict_core.step_interval_seconds` with `execution.post_action_delay_seconds`.
- `fsq_agent/core/SPEC.md`: move pacing responsibility from `StepSequenceRunner` to `StepRunner` and define delay ordering between invoke and finalize.
- `fsq_agent/agent/SPEC.md`: require dynamic `StepRunner` construction to use the configured delay policy.
- `fsq_agent/cli/SPEC.md`: update strict-core helper signatures and strict execution wording.
- `fsq_agent/playground/SPEC.md`: update strict playground execution wording if its SPEC documents strict pacing.
- `fsq_agent/tools/SPEC.md`: only if SPEC review wants to document CommonTool decorator override behavior explicitly.

Config examples and README snippets should also change from `harness.strict_core.step_interval_seconds` to the new `execution.post_action_delay_seconds` shape.

## Error Handling And Edge Cases

Negative config values and negative decorator/catalog values are configuration errors.

`None` decorator values must not be serialized as zero. `None` means inherit; `0` means explicitly disable.

If a capability fails before any backend side effect, a positive delay may still run because `StepRunner` only has normalized phase information. This is acceptable unless implementation can cheaply distinguish validation-only failures without adding executor-specific branches.

If artifact capture fails after the delay, the result remains an `artifact_error` as today. The delay does not mask or downgrade artifact failures.

If a strict normal step fails and teardown follows, teardown still runs. The failed step's post-action delay should occur before failure evidence and before teardown begins when the effective delay is greater than zero.

Zero delay should not call `time.sleep(0)`.

Tests should monkeypatch runner-module sleep to avoid real delays.

## Verification Expectations

Focused tests should cover:

- config accepts `execution.post_action_delay_seconds.platform` and `.common`, with defaults `1.0` and `0.0`, and rejects negatives,
- old strict-only config wording and tests are updated or replaced,
- capability decorators and catalog definitions propagate `post_action_delay_seconds` into `CapabilityDefinition`, preserving `None` versus `0`,
- `CapabilityDefinition.safe_metadata()` includes the delay override field,
- `StepRunner` delays after harness/driver invoke and before `after_action` plus after-action evidence capture,
- after-action screenshot/UI-tree capture occurs after the delay,
- `StepRunner` applies platform config defaults when a harness/driver capability has no override,
- `StepRunner` honors capability override `0` for read-only platform capabilities,
- CommonTools do not delay by default,
- a CommonTool capability override can opt into delay,
- `StepSequenceRunner` no longer performs configured inter-step sleep,
- dynamic `HarnessToolAdapter` and strict CLI/playground construction pass the same delay policy into `StepRunner`,
- no generated strict replay YAML contains synthetic `waitMs` commands from this pacing behavior.

Recommended focused command after implementation:

```bash
./.venv/Scripts/python.exe -m pytest tests/test_config.py tests/test_capabilities.py tests/test_step_runner.py tests/test_step_sequence_runner.py tests/test_cli_core_execution.py tests/test_cli.py tests/test_openai_runtime.py tests/test_playground.py
```

Broader verification should run the project test suite when the SPEC update touches shared models and capability discovery.

## Open Questions Resolved

- Scope: dynamic and strict execution must both use the new delay behavior.
- Control surface: decorator/capability metadata controls per-capability override.
- Defaults: platform defaults to configured delay; CommonTool defaults to zero.
- Config shape: `execution.post_action_delay_seconds` is the preferred YAML path.
- Evidence ordering: delay must happen before after-action and failure evidence capture.
- Replay behavior: delay must not become generated `waitMs` or any other synthetic command.

## Handoff

Next step: update the affected `SPEC.md` files from this confirmed design, request SPEC confirmation, then implement against the confirmed specs.