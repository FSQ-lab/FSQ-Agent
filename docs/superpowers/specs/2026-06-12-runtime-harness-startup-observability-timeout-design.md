# Runtime Harness Startup Observability and Timeout Design

Date: 2026-06-12
Status: Confirmed design

## Goal

Eliminate the silent gap after dynamic pre-planning and before main task execution starts. When a dynamic LLM run transitions from `Goal pre-plan injected` into main execution, users should see explicit runtime startup progress and should not wait indefinitely if synchronous harness construction blocks.

The immediate motivating case is `fsq-agent: run case yaml (LLM raw)` with the Android uiautomator2 backend. The latest run produced a good raw-case pre-plan, including the authored `Microsoft services` item, but then emitted no main execution events. Code inspection shows `OpenAIAgentsRuntime.run_task()` constructs the provider, harness, harness adapter, CommonTool tools, and SDK agent before emitting the existing main `Planning started` event. The Android harness path constructs `UiAutomator2AndroidDriver`, whose constructor synchronously calls `uiautomator2.connect(serial)` when no device is injected. A block in this path currently appears as a silent stall.

## Scope

This design covers the dynamic LLM main execution startup path owned by `agent`:

- provider/session setup progress visibility,
- harness construction progress visibility,
- action-space and SDK tool assembly progress visibility,
- SDK agent readiness before streamed planning begins,
- timeout bounding for synchronous harness construction using the existing `agent.step_timeout_seconds` setting.

The intended implementation changes are limited to `agent` runtime orchestration and tests, plus any required `agent/SPEC.md` update during the later spec-driven phase.

## Non-Goals

This design does not change raw case pre-planning behavior. The raw YAML planning-reference fix remains a separate completed design and implementation.

This design does not add new YAML configuration fields. It reuses `agent.step_timeout_seconds` as the startup harness construction timeout to keep the first iteration small and compatible with existing local config.

This design does not change the public constructor or public contract of `UiAutomator2AndroidDriver`.

This design does not define per-action UI timeout behavior, locator retry policy, uiautomator2 connection tuning, Android serial discovery, Appium MCP lifecycle behavior, or driver-specific skip-initialization capabilities.

This design does not make strict-core execution asynchronous and does not alter deterministic strict replay behavior.

## Proposed Design

### Approach Selected

Use observable runtime startup events plus a bounded harness construction wrapper.

The runtime should emit progress events before and during main execution startup, then perform synchronous harness construction in an async-compatible wrapper. The wrapper should execute the blocking `_build_harness(run_id)` call in a worker thread and apply `asyncio.wait_for(..., timeout=settings.agent.step_timeout_seconds)` around it.

This provides two improvements at once:

- The run timeline shows whether the process reached provider setup, harness setup, tool setup, and SDK planning startup.
- If harness construction blocks longer than the configured startup timeout, the run fails with structured evidence instead of remaining invisible until an operator manually interrupts it.

### Alternatives Considered

#### Approach A: Observability Only

Emit startup events around provider, harness, tool, and SDK agent construction, but leave harness construction unbounded.

Trade-off: This is the smallest change and would identify the stuck phase, but it would still require manual interruption when uiautomator2 connection blocks. It improves diagnosis but not operational behavior.

#### Approach B: Observability plus Harness Setup Timeout

Emit startup events and bound harness construction with the existing `agent.step_timeout_seconds` setting.

Trade-off: This solves the current silent-stall problem without expanding configuration. It also preserves existing module boundaries because `agent` already owns runtime startup and already depends on `core` harness construction. This is the selected design.

#### Approach C: Approach B plus Driver Connection Configuration

Add driver-specific configuration such as uiautomator2 connect timeout, serial probing, or backend readiness checks.

Trade-off: This may be useful later, but it expands the config and core driver contracts. The current failure can be made visible and bounded without committing to a driver-specific public interface.

## Control Flow

The dynamic execution path should become:

1. `FsqAgent.run()` emits the existing run start and context-loaded events.
2. If needed, internal pre-plan emits existing pre-plan events and injects key actions.
3. `OpenAIAgentsRuntime.run_task()` validates runtime settings.
4. The runtime emits a main execution startup event before provider and platform setup work begins.
5. Provider session construction happens as today. If this raises, the existing failed-step behavior applies, with the failure event identifying the startup path.
6. The runtime emits a harness setup started event with safe metadata such as platform, backend, app id presence, serial presence, and timeout seconds. It must not expose secrets.
7. Harness construction runs through a helper that calls `_build_harness(run_id)` in a worker thread and applies `agent.step_timeout_seconds` as the timeout.
8. On successful harness construction, the runtime emits a harness setup completed event with safe metadata such as platform, backend, and driver class when available.
9. The runtime builds `HarnessToolAdapter`, CommonTool tools, harness tools, and the SDK `Agent`, emitting progress events for tool setup and agent readiness.
10. The runtime emits the existing main `Planning started` event immediately before invoking `Runner.run_streamed(...)`.
11. Streamed SDK events proceed as they do today.

## Public Behavior

Users running `fsq-agent run --case-yaml ... --stream-format jsonl` should see additional JSONL events after pre-plan injection and before main model planning starts. A stalled harness setup should no longer appear as a blank terminal.

The new events are runtime progress events, not model reasoning and not execution proof. They should be suitable for CLI streaming, persisted event timelines, reports, and troubleshooting.

If harness construction exceeds the timeout, the CLI run should complete as a failed run rather than silently hanging. The failed output should identify harness setup timeout as the failure and include the configured timeout seconds.

## Module Ownership

`agent` owns the change because `OpenAIAgentsRuntime` owns dynamic runtime startup, provider session creation, harness construction, harness tool adaptation, SDK agent construction, stream event mapping, and failed `StepResult` conversion.

`config` does not need new public settings for this iteration. It already exposes `AgentSettings.step_timeout_seconds`, and that setting can serve as the startup harness construction timeout.

`core` does not need public interface changes. `UiAutomator2AndroidDriver` can remain synchronous and narrow; `agent` can bound synchronous construction from the outside.

`cli` does not need command-line changes. The existing stream and event logger paths should receive the new events through the same `RunEvent` flow.

## Error Handling

Harness construction exceptions should continue to be converted into a failed runner `StepResult`, preserving the current high-level behavior that reports can still be generated.

Harness construction timeout should be treated as a startup failure. The runtime should emit a `run_failed` event and return a failed `StepResult` with:

- `status="failed"`,
- `tool_name="openai_agents.runner"`,
- a concise `actual_outcome` indicating main execution startup failed,
- an `error` message identifying harness setup timeout and timeout seconds,
- `duration_ms` based on elapsed runtime.

If `_build_harness()` eventually finishes in the worker thread after the timeout, its result should be ignored. No UI actions should be invoked from the timed-out path after the runtime has returned a failed step.

Cancellation and keyboard interruption should continue to propagate through `FsqAgent.run()` so its existing `BaseException` handling emits final run failure events.

## Edge Cases

Injected test harness factories should continue to work. A harness factory that succeeds quickly should not pay meaningful overhead beyond thread scheduling.

A harness factory that raises synchronously should produce a failed runner step and a visible failure event.

A harness factory that blocks should produce a timeout failure after `agent.step_timeout_seconds`.

If provider session creation itself blocks before harness setup, this design's startup event still shows that main execution startup began, but provider-specific timeout control remains out of scope.

If CommonTool or harness tool schema assembly fails after harness construction, existing failed-step conversion should remain in place, and the new startup events should make the last completed phase visible.

## Affected Specs Expected To Change

- `fsq_agent/agent/SPEC.md`: document startup progress events and bounded harness construction in the dynamic runtime design decisions and error handling.

No root `SPEC.md`, `config/SPEC.md`, `core/SPEC.md`, or `cli/SPEC.md` changes are expected for this iteration unless spec-driven review identifies a mismatch.

## Verification Expectations

Focused tests should cover:

- successful runtime startup emits provider/harness/tool/agent progress before the existing main `Planning started` event,
- harness construction timeout returns a failed runner step and emits a failure event,
- harness construction exception returns a failed runner step and emits a failure event,
- existing runtime failure behavior still returns a failed `StepResult`,
- existing raw-case planning-reference tests continue to pass.

The final verification command set should include focused agent/runtime tests and the full test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_openai_runtime.py tests\test_agent.py
.\.venv\Scripts\python.exe -m pytest
```

After implementation, rerun the launch-equivalent raw case command. The expected improvement is that the run timeline advances past `Goal pre-plan injected` into explicit main startup or harness setup events. If the Android backend is unavailable or uiautomator2 connection blocks, the run should fail after the configured timeout with a useful event and failed step instead of requiring manual interruption.

## Open Questions Resolved

- Scope selected: Approach B, observable startup events plus harness setup timeout.
- Timeout source: reuse existing `agent.step_timeout_seconds`; do not add new config yet.
- Driver API: do not change `UiAutomator2AndroidDriver` public constructor or core driver contract in this iteration.
- Raw case planning: keep separate and unchanged.

## Handoff

Next step: translate this confirmed design into `fsq_agent/agent/SPEC.md` updates using the spec-driven workflow. Implementation must wait until those SPEC updates are confirmed.
