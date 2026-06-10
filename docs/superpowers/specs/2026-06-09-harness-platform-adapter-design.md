# Harness and Platform Adapter Design

Status: draft for review
Date: 2026-06-09
Scope: design for replacing lifecycle-controller-driven platform setup and direct MCP action exposure with a Harness plus PlatformAdapter abstraction
Language policy: English is the contract source of truth. Chinese notes are included where they clarify review decisions and should remain aligned with the English design.

## 1. Goal

FSQ-Agent should stop treating MCP tools as the public platform-action interface. Platform automation should be exposed through FSQ-owned harness and platform action contracts, while backend transports remain implementation details.

This design replaces the current `LifecycleController` concept with two explicit abstractions:

- `Harness`: the test-runtime facade and lifecycle owner.
- `PlatformAdapter`: the platform-operation engine owned by a harness.

The first implementation target is Android. Android may use an internal Appium-based backend during the migration, but the public configuration, prompt contract, agent-visible tool names, reports, and future StepRunner API must not depend on MCP concepts.

中文摘要：上层不再把 MCP 当作动作接口。`Harness` 负责测试运行生命周期，`PlatformAdapter` 负责平台注册和执行动作。Android 第一版可以在内部临时用 Appium MCP client，但这个细节不能进入配置、prompt、LLM 工具名或 StepRunner contract。

## 2. Current State

The current tools module exposes three related concerns through MCP and lifecycle code:

- MCP server configuration and SDK-managed MCP tool exposure.
- Deterministic setup and teardown through `LifecycleController`.
- Appium Android session and app lifecycle management through MCP tool calls.

The current Android lifecycle controller owns session creation, app activation, app termination, keyboard cleanup, alert cleanup, session deletion, and model-visible runtime policy text. This works for the present Appium MCP path, but it couples platform runtime semantics to MCP server/tool details.

The desired v2 shape is:

```text
External caller
  -> Harness
       -> PlatformAdapter
            -> backend transport
```

The backend transport may temporarily use an internal MCP client. It is not part of the public harness contract.

## 3. Scope

This design covers:

- Replacing the top-level `lifecycle` configuration with top-level `harness` configuration.
- Replacing `LifecycleController` with a `Harness` abstraction.
- Introducing `PlatformAdapter` as the platform action registry and action invocation abstraction.
- Ensuring the same registered platform actions can be consumed by the current OpenAI Agents SDK loop and by the future shared execution core.
- Defining Android MVP behavior with `AndroidHarness` plus `AndroidAppiumPlatformAdapter`.
- Hiding backend transport details from configuration, prompts, agent-visible tools, reports, and StepRunner contracts.

This design does not update root or module `SPEC.md` files. After review, the next workflow step is to translate this design into SPEC changes.

## 4. Non-Goals

This design does not implement:

- The full shared execution core, `StepBuilder`, or `StepRunner`.
- Complete cross-platform support for Android, Web, iOS, and desktop.
- The full original `HarnessInterface` seven-method contract.
- A complete evidence bundle schema.
- Backward compatibility for the old `lifecycle` configuration.
- Direct removal of every backend dependency from implementation code in the first migration.

The first migration may still use an internal backend client for Android. Future versions should remove that backend once a direct platform client is available.

## 5. Confirmed Design Decisions

### 5.1 Use Two Abstractions

`HarnessInterface` is too broad as a single public concept because it mixes test lifecycle and platform operations. The design uses two names instead:

- `Harness` for test-runtime lifecycle, policy, and action-call wrapping.
- `PlatformAdapter` for platform action definition and concrete platform execution.

### 5.2 Harness Owns the Adapter

The harness holds or creates the platform adapter. External callers should use the harness, not the adapter directly.

```text
Agent loop / StepRunner
  -> Harness.action_space()
  -> Harness.invoke_action(...)
       -> Harness.before_action(...)
       -> PlatformAdapter.invoke_action(...)
       -> Harness.after_action(...)
       -> PlatformActionResult
```

This guarantees that lifecycle hooks, event emission, action policy, and failure classification are not bypassed.

### 5.3 Backend Details Are Hidden

Backend transport details must not appear in the public contract. In particular:

- Harness configuration must not expose backend server names or backend tool names.
- Agent-visible tools must use FSQ/platform action names, not backend tool names.
- Runtime policy must describe platform behavior, not backend protocol mechanics.
- Reports and events should use harness/platform/action terminology as their user-facing subject.
- Backend-specific diagnostics may appear only as bounded debug metadata.

### 5.4 No Lifecycle Compatibility Layer

The migration is a breaking configuration change. The top-level `lifecycle` configuration is replaced by top-level `harness` configuration. The design does not require a compatibility period where old lifecycle settings are mapped into the new harness settings.

### 5.5 One Action Registry, Two Consumers

The platform action registry must support both:

- Current OpenAI Agents SDK function-tool exposure.
- Future deterministic `StepRunner` invocation.

The design should avoid creating one action schema for LLM tools and a separate action schema for the execution core.

## 6. Proposed Configuration

The new top-level configuration shape should be platform semantic rather than backend semantic:

```yaml
harness:
  name: android
  options:
    case_reset: terminate_and_activate
    teardown_cleanup:
      hide_keyboard: true
      dismiss_alert: true
      terminate_app: true
  platform:
    type: android
    automation: appium
    capabilities_config_env: CAPABILITIES_CONFIG
    session_create_attempts: 3
    session_create_retry_delay_seconds: 2.0
```

Configuration semantics:

- `harness.name` selects the test-runtime harness, such as `none`, `android`, `web`, or `ios`.
- `harness.options` controls lifecycle policy, such as case reset and teardown cleanup behavior.
- `harness.platform.type` selects the platform family.
- `harness.platform.automation` selects the automation technology at a semantic level, such as `appium` or `playwright`.
- `harness.platform.capabilities_config_env` names an environment variable that points to platform/device/app capability data.
- `harness.platform.session_create_attempts` and `harness.platform.session_create_retry_delay_seconds` configure platform session startup retry behavior without exposing backend transport.

The configuration must not require the operator to configure backend-specific platform action tools. Platform automation actions are registered by the platform adapter selected by the harness configuration.

中文备注：新的配置描述“我要跑 Android + Appium 自动化”，不描述“我要连哪个 MCP server / 调哪个 MCP tool”。

Platform action execution must not depend on user-configured backend server settings. During implementation, any temporary backend wiring used by `AndroidAppiumPlatformAdapter` is internal to that adapter and should be removable in a future version without changing the `harness` configuration.

## 7. Core Interfaces

The names below describe contract shape. Exact signatures should be finalized in the SPEC update.

### 7.1 Harness

`Harness` is the external runtime facade.

Responsibilities:

- Own run-level and case-level lifecycle.
- Own action-level hooks.
- Hold the platform adapter.
- Expose the platform action space upward.
- Invoke actions through the adapter while preserving lifecycle hooks.
- Provide runtime policy text for the agent and execution core.

Conceptual methods:

```text
action_space() -> list[PlatformActionDefinition]
invoke_action(action_name, params, context) -> PlatformActionResult
run_setup(context) -> None
run_teardown(context) -> None
case_setup(task, context) -> None
case_teardown(task, context) -> None
before_action(action_call, context) -> None
after_action(action_call, result, context) -> None
runtime_policy() -> list[str]
```

`before_action` and `after_action` belong to the harness because they are test-runtime hooks, not platform operation definitions. Default implementations may be no-ops.

### 7.2 PlatformAdapter

`PlatformAdapter` is the platform-operation engine.

Responsibilities:

- Register platform actions.
- Expose action definitions and JSON schemas.
- Execute platform actions.
- Hide backend transport details.
- Normalize backend responses into `PlatformActionResult`.

Conceptual methods:

```text
action_space() -> list[PlatformActionDefinition]
invoke_action(action_name, params, context) -> PlatformActionResult
```

Platform adapters should not decide whether a test case passed. They should report action facts and failures.

### 7.3 PlatformActionDefinition

Each registered action should be represented with one shared definition that can be converted to an SDK function tool or consumed directly by the future StepRunner.

Required fields:

```text
name
description
input_schema
visibility
idempotent
timeout_seconds
evidence_policy
```

`visibility` controls who may call the action:

- `agent_visible`: can be exposed as an LLM-callable tool.
- `runner_only`: available to the shared execution core but not exposed to the LLM.
- `lifecycle_only`: available only to harness lifecycle code.

### 7.4 PlatformActionResult

Action results should be structured enough for reports and future evidence bundles.

Required fields:

```text
action_name
status
duration_ms
output
error
failure_category
evidence_refs
backend_debug
```

`backend_debug` may include bounded diagnostic metadata for maintainers, but it must not become a model-facing operating contract.

## 8. Control Flow

### 8.1 Current Agent Runtime Flow

The current OpenAI Agents SDK loop should consume harness actions as function tools:

```text
Settings.harness
  -> HarnessFactory.create(...)
  -> Harness.run_setup(...)
  -> Harness.case_setup(task, ...)
  -> Harness.action_space()
  -> AgentsToolFactory wraps agent_visible actions as FunctionTool
  -> LLM calls an FSQ/platform action tool
  -> FunctionTool calls Harness.invoke_action(...)
  -> Harness.before_action(...)
  -> PlatformAdapter.invoke_action(...)
  -> Harness.after_action(...)
  -> PlatformActionResult
  -> RunEvent / artifact / report evidence
  -> Harness.case_teardown(task, ...)
  -> Harness.run_teardown(...)
```

The agent should see platform action names such as `android_tap`, `android_input_text`, `android_press_key`, `android_back`, `android_wait`, `android_find_element`, `android_scroll_to_element`, `android_scroll`, `android_get_text`, `android_get_attribute`, `android_page_source`, `android_window_size`, and `android_screenshot`.

The agent should not see backend lifecycle or session-management actions.

### 8.2 Future Shared Execution Core Flow

The future shared execution core should reuse the same harness entry point:

```text
StepRunner
  -> Harness.invoke_action(...)
       -> Harness.before_action(...)
       -> PlatformAdapter.invoke_action(...)
       -> Harness.after_action(...)
  -> EvidenceBundle
  -> Verifier
```

The StepRunner must not need to know which backend transport the adapter uses.

## 9. Android MVP

The first implementation target should be Android:

```text
AndroidHarness
  -> AndroidAppiumPlatformAdapter
       -> internal backend client, temporary
```

`AndroidHarness` owns lifecycle policy:

- Run setup creates or validates the Android automation session through the adapter.
- Case setup restores the application under test according to `case_reset`.
- Case teardown performs configured cleanup such as hiding the keyboard, dismissing alerts, and terminating the app.
- Run teardown closes the automation session.
- Action hooks wrap all agent-visible or runner-invoked actions.

`AndroidAppiumPlatformAdapter` owns Android action registration and concrete platform execution:

- Register agent-visible actions such as tap, input text, press key, back, wait, find element, and screenshot.
- Register lifecycle-only capabilities such as session creation, session deletion, app activation, app termination, app state query, keyboard cleanup, and alert cleanup.
- Read Android app identifiers from the configured capabilities source.
- Normalize backend responses into platform action results.

Session and app lifecycle capabilities belong to the adapter because they are platform operations, but their visibility is `lifecycle_only`, so they are not exposed as LLM-callable tools.

## 10. Error Handling

Failure classification should be platform semantic rather than backend semantic.

Recommended first categories:

```text
configuration_error
lifecycle_error
unsupported_action
action_error
observation_error
timeout_error
backend_error
unknown_error
```

Category meanings:

- `configuration_error`: required harness, platform, capabilities, or environment configuration is missing or invalid.
- `lifecycle_error`: run or case setup/teardown failed.
- `unsupported_action`: the requested action is not registered in the harness action space or is not visible to the caller.
- `action_error`: a platform action such as tap, input, back, or press key failed.
- `observation_error`: screenshot, UI tree, element lookup, or other observation failed.
- `timeout_error`: a platform operation exceeded its timeout.
- `backend_error`: the hidden backend failed in a way that cannot be cleanly normalized into a more specific platform category.
- `unknown_error`: the harness cannot classify the failure reliably.

The harness should decide whether lifecycle hook failures are fatal. For Android MVP, setup failures should be fatal; teardown cleanup failures such as hiding the keyboard or dismissing alerts may be non-fatal if configured that way.

## 11. Events and Evidence

The event timeline should use harness and platform terminology. Recommended event types include:

```text
harness_setup_started
harness_setup_completed
harness_setup_failed
harness_teardown_started
harness_teardown_completed
harness_teardown_failed
platform_action_started
platform_action_completed
platform_action_failed
```

Events should include structured fields such as:

```text
action_name
action_arguments
duration_ms
status
failure_category
evidence_refs
backend_kind
backend_debug_preview
```

User-facing event titles and messages should describe harness or platform actions. Backend details may be recorded in debug metadata for diagnosis but should not be the primary timeline subject.

`PlatformActionResult.evidence_refs` is intentionally lightweight in this design. The later shared execution core and report SPEC updates should define how these refs become part of the authoritative evidence bundle.

## 12. Affected Specs Expected To Change

After this design is approved, the `spec-driven` workflow should update at least these specs:

- Root `SPEC.md`: module navigation may need to mention the harness/platform-action direction if public architecture changes.
- `fsq_agent/models/SPEC.md`: replace `LifecycleControllerSettings` with harness/platform settings and add shared action definition/result models.
- `fsq_agent/config/SPEC.md`: replace top-level `lifecycle` configuration with `harness` configuration.
- `fsq_agent/tools/SPEC.md`: replace lifecycle controller public interface with harness and platform adapter interfaces; update action exposure and backend-hiding rules.
- `fsq_agent/agent/SPEC.md`: update runtime construction so platform actions come from the harness and agent-visible tools are FSQ/platform actions.
- `fsq_agent/report/SPEC.md`: update event/report terminology from backend tool calls to harness/platform action records where applicable.

## 13. Open Questions Resolved During Review

Resolved decisions:

- The design uses `PlatformAdapter` plus `Harness`, not a single broad `HarnessInterface`.
- The harness holds the platform adapter.
- External callers should use `Harness.invoke_action`, not call the adapter directly.
- `before_action` and `after_action` belong to the harness.
- Platform adapter methods are shared by current LLM tool exposure and future StepRunner invocation.
- The old `lifecycle` configuration is replaced directly; no compatibility layer is required.
- Backend transport details are hidden from configuration and public contracts.
- Android lifecycle/session capabilities are platform adapter capabilities marked `lifecycle_only`.
- Android MVP may use an internal backend client temporarily, but future versions should remove it without changing the public harness contract.

## 14. Verification Expectations

The implementation that follows this design should be verifiable by focused tests and configuration checks:

- Loading settings accepts the new `harness` shape and rejects the removed `lifecycle` shape.
- `HarnessFactory` creates a no-op harness and Android harness from settings.
- `AndroidHarness.action_space()` exposes agent-visible Android actions and excludes lifecycle-only actions from LLM tool construction.
- `Harness.invoke_action()` calls `before_action`, delegates to the adapter, then calls `after_action`.
- Unsupported actions return or raise a structured `unsupported_action` failure.
- Android run setup and teardown map to adapter lifecycle-only capabilities.
- Agent runtime builds function tools from harness action definitions rather than directly from backend platform tools.
- Run events for platform actions use harness/platform terminology.
- Backend debug metadata is bounded and diagnostic-only.
- Future StepRunner tests can invoke the same harness action contract without depending on backend transport.

## 15. Handoff

This document is a reviewed design candidate, not the implementation source of truth. Once approved, use `spec-driven` to translate it into root and module `SPEC.md` updates before implementation begins.

Design document: docs/superpowers/specs/2026-06-09-harness-platform-adapter-design.md
Next step: use spec-driven to update root/module SPEC.md files from this design.