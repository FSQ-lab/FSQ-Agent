# Agent, Common, And Platform Tool Boundary Design

Date: 2026-06-30
Status: Ready for spec-driven handoff

## Goal

Clarify and simplify fsq-agent tool ownership by separating dynamic-only agent helper tools from recordable execution capabilities.

The target terminology is:

- AgentTool: dynamic OpenAI Agents SDK helper tools used only by the agent during live execution. AgentTools are not strict replay capabilities and are never recorded into generated FSQ YAML.
- CommonTool: recordable execution capabilities that every active platform receives by default, currently `wait_ms`/`waitMs` and `get_runtime_secret`/`runtimeSecret` dependency metadata.
- PlatformTool: recordable platform-specific execution capabilities, including driver-backed actions such as Android `tap_on` and Web `click_on`, plus backend-owned assertions such as `assert_with_ai`.

`HarnessInterface` remains a long-term core contract. Its `invoke_action(step, context)` method stays as the stable execution gateway used by `StepRunner` to invoke active-platform behavior. The change is that concrete harness classes such as `AndroidHarness` and `WebHarness` should no longer directly implement individual tool bodies such as `_assert_with_ai`; they should route CommonTools to platform providers and backend PlatformTools to concrete backend drivers while continuing to provide runtime services such as context, artifact capture, driver access, evaluator injection, and error classification.

Correction from implementation review: in this design, “platform” capability exposure for backend operations means concrete backend classes such as `UiAutomator2AndroidDriver` and `PlaywrightWebDriver`. Shared AI assertion logic may be factored into a reusable support class, but the decorated `assert_with_ai` tool method belongs on the concrete backend class. `AndroidPlatformTools` and `WebPlatformTools` are unnecessary once platform-specific behavior has moved to backend drivers; the remaining common provider can be platform-bound `CommonPlatformTools`.

## Scope

In scope:

- Rename the dynamic-only local helper tool concept from CommonTool to AgentTool.
- Reserve CommonTool for platform-default recordable capabilities shared by every platform.
- Introduce platform tool providers that combine inherited CommonTools with platform-specific PlatformTools.
- Move AI assertion behavior out of concrete harness classes and into backend tool ownership, while still using harness runtime services for screenshot/artifact capture.
- Keep `HarnessInterface.invoke_action` as the long-term invocation entry point for `StepRunner`.
- Update registry, SDK exposure, event metadata, and recording semantics so AgentTools are dynamic-only and recordable behavior is driven by capability replay metadata.
- Preserve strict replay support for `waitMs`, runtime-secret references, platform action aliases, and `assertWithAI`.

Affected modules and specs:

- Root `SPEC.md`: project terminology, module table, capability execution, recording, architecture diagram, and development rules.
- `fsq_agent/models/SPEC.md`: shared metadata terminology and any model contract changes needed for AgentTool definitions, CommonTool capabilities, and PlatformTool capabilities.
- `fsq_agent/capabilities/SPEC.md`: decorator helper names and ownership rules for common/platform capability declarations.
- `fsq_agent/tools/SPEC.md`: repurpose current dynamic local helper tool ownership as AgentTool ownership, or introduce a replacement `agent_tools` module and document migration compatibility.
- `fsq_agent/core/SPEC.md`: `HarnessInterface` role, platform CommonTool provider ownership, backend tool ownership, common tool mixin ownership, `StepRunner` routing expectations, and platform blocks.
- `fsq_agent/agent/SPEC.md`: dynamic SDK tool assembly from AgentTools plus active platform capability schemas.
- `fsq_agent/cli/SPEC.md`: strict registry composition and dynamic recording behavior.
- `fsq_agent/fsq/SPEC.md`: strict parsing against active platform capabilities plus shared CommonTool aliases such as `waitMs`.
- `fsq_agent/report/SPEC.md` may need terminology updates for reconstructed tool-call origin names.
- `fsq_agent/playground/SPEC.md` may need terminology updates if it presents active capability/tool lists.

## Non-Goals

This design does not update implementation code or `SPEC.md` files. The next SDD step is to translate this design into SPEC updates, confirm those SPEC changes, then implement.

This design does not remove `HarnessInterface`, `invoke_action`, `get_context`, `capture_artifact`, or platform harness construction. Harness classes remain the runner-facing runtime gateway.

This design does not add new test automation capabilities beyond rehoming current concepts. It does not add locator recovery, AI repair, testcase mutation, shell execution, or new platform families.

This design does not make AgentTools available in strict replay. File reads, file writes, artifact search, and artifact slice reads are dynamic agent helpers only unless a later SPEC explicitly promotes one of them to a recordable execution capability.

This design does not require every future platform to support screenshots. Screenshot/artifact support is required only for platforms that expose screenshot evidence or visual assertion PlatformTools such as `assert_with_ai`.

## Selected Approach

Use explicit tool families and make the active platform tool provider the owner of recordable execution capabilities.

Dynamic SDK surface:

```text
OpenAIAgentsRuntime
  exposes AgentTools
  exposes active platform capability schemas
```

Strict replay surface:

```text
active platform capability registry
  includes CommonTools inherited by every platform
  includes PlatformTools for the selected platform only
  excludes AgentTools
```

Core execution surface:

```text
StepRunner
  resolves capability metadata
  prepares context/evidence/delay policy
  calls HarnessInterface.invoke_action(step, context)

HarnessInterface implementation
  delegates concrete behavior to active platform tool provider
  supplies runtime services such as context, artifact capture, driver access, settings, and classification
```

This keeps the existing `StepRunner -> HarnessInterface.invoke_action` boundary while removing per-tool bodies from concrete harness classes. A harness implementation becomes a stable runtime gateway and service provider. A platform tool provider owns inherited CommonTool implementations; concrete backend drivers own backend PlatformTool implementations.

## Approaches Considered

### Approach A: Rename Current CommonTool To AgentTool Only

This would rename the current `tools` module concepts and leave `wait_ms` and `get_runtime_secret` beside file/artifact helper tools.

Trade-off: low implementation churn, but it does not satisfy the requirement that CommonTool become the platform-default recordable tool family. It also keeps dynamic-only and replayable tools mixed in one provider.

Decision: rejected.

### Approach B: Platform Tool Provider With CommonTool Mixin

Create active platform tool providers that inherit shared CommonTool implementations and add platform-specific PlatformTools. Harness classes delegate `invoke_action` to these providers and retain runtime services.

Trade-off: moderate SPEC and implementation churn across core, agent, cli, tools, and tests. It directly matches the desired ownership model and reduces conceptual layers by removing harness-owned tool bodies.

Decision: selected.

### Approach C: Put All Recordable Tool Bodies Directly In Harness Classes

Concrete harness classes would inherit a common mixin and implement platform-specific methods directly.

Trade-off: simple call path, but it conflicts with the clarified requirement that `AndroidHarness` and `WebHarness` should not implement concrete tool bodies such as `_assert_with_ai`. It also makes harness classes grow with every platform feature.

Decision: rejected.

## Architecture And Module Ownership

### AgentTool Ownership

AgentTools are dynamic-only SDK helper tools. They should not produce `CapabilityDefinition` records for strict replay and should not be registered in the FSQ capability registry.

Target AgentTools:

- `read_file`
- `write_file`
- `search_artifact`
- `read_artifact_slice`

AgentTool behavior includes scoped file safety, bounded artifact reads, output artifacting for large model-facing responses, and redaction rules for helper output when needed. AgentTool events should use a distinct origin such as `agent` or `agent_tool` so reports and recorders can distinguish them from recordable execution capabilities.

Implementation ownership can either repurpose the current `fsq_agent.tools` package to AgentTool terminology or introduce a new `fsq_agent.agent_tools` package with compatibility shims. The SPEC update should choose one path explicitly. The preferred target name is AgentTool at the public concept/API level even if compatibility imports remain during migration.

### CommonTool Ownership

CommonTools are recordable default capabilities available on every platform. They are not dynamic-only helper tools.

Target CommonTools:

- `wait_ms` with alias `waitMs`, using `WaitMsParams`, `ReplayPolicy(kind="fsq_command", alias="waitMs")`, and bounded elapsed-time sleep semantics.
- `get_runtime_secret` with dependency replay alias `runtimeSecret`, sensitivity metadata, allowlisted environment-name lookup, and secret-value redaction in persisted outputs.

CommonTool implementations should live in a shared mixin or base provider that platform tool providers inherit. This gives Android, Web, and future platforms the default methods without requiring duplicate implementations. The mixin must be state-aware enough to access injected runtime-secret settings or a secret resolver, and it must return normalized sensitive results that preserve current redaction and dependency metadata behavior.

CommonTool definitions should be discovered from the active platform tool provider, not from AgentTool providers.

### PlatformTool Ownership

PlatformTools are recordable capabilities that are specific to one platform. They include both driver-backed mechanics and platform-level behavior that is not a driver method.

Examples:

- Android driver-backed PlatformTools: `launch_app`, `kill_app`, `tap_on`, `input_text`, `press_key`, `swipe`, `assert_visible`, `assert_not_visible`, `assert_state`, `ui_tree`.
- Web driver-backed PlatformTools: `start_browser`, `close_browser`, `navigate_to`, `click_on`, `type_text`, `wait_for`, `take_screenshot`, `page_snapshot`, `assert_visible`, `assert_text`.
- Platform-level PlatformTools: `assert_with_ai` for Android and Web.

Driver-backed PlatformTools may still delegate to concrete driver methods. Platform-level tools such as `assert_with_ai` may use harness runtime services, provider-backed evaluator injection, artifact capture, and context metadata. They should not be implemented as private methods on `AndroidHarness` or `WebHarness`.

### HarnessInterface Ownership

`HarnessInterface` remains in `core.harness` and remains the runner-facing runtime interface.

Long-term responsibilities:

- Build or expose current `HarnessContext`.
- Expose active action/capability schemas through `action_space()` or a future renamed equivalent.
- Receive `invoke_action(step, context)` calls from `StepRunner`.
- Delegate concrete capability execution to the active platform tool provider.
- Provide lifecycle hooks `before_action` and `after_action`.
- Capture artifacts requested by `StepRunner` or PlatformTools.
- Classify platform/runtime exceptions.

Non-responsibilities:

- Owning concrete tool bodies such as `_assert_with_ai`.
- Deciding dynamic recording eligibility by tool name.
- Constructing SDK FunctionTool objects.
- Parsing FSQ YAML.
- Owning provider construction.

## Capability Metadata And Decorators

The shared `capabilities` module should remain the declaration layer. It should support readable domain helpers for the new families while keeping one metadata contract.

Required declaration concepts:

- AgentTool declarations or definitions for dynamic-only SDK tools. These should not carry `ReplayPolicy` and should not enter strict capability registries.
- CommonTool declarations for platform-default recordable methods.
- PlatformTool declarations for platform-specific recordable methods.

The target SPEC should decide whether this requires changing `CapabilityExecutorKind` values or whether a new safe metadata field is sufficient during migration. The design preference is to make recordable tool family explicit as `common` or `platform`, while retaining enough implementation metadata to distinguish driver-backed PlatformTools from platform-level PlatformTools.

Implementation details such as `driver_method`, backend, platform, replay alias, evidence capture, step kind, sensitivity, strict schema mode, and post-action delay override should remain capability metadata and should be consumed by registries, SDK adapters, FSQ parsing, recorders, and reports.

## Data And Control Flow

### Dynamic Run

1. Entry/runtime code loads settings and constructs the active harness, active platform tool provider, and AgentTool provider.
2. The active platform tool provider contributes CommonTool and PlatformTool capability definitions.
3. `OpenAIAgentsRuntime` builds SDK FunctionTools from:
   - AgentTool definitions for dynamic-only helper tools.
   - Active platform action schemas for CommonTool and PlatformTool capabilities.
4. When the model calls an AgentTool, the AgentTool adapter executes it directly through AgentTool infrastructure, emits AgentTool-origin events, and never produces replay metadata.
5. When the model calls a CommonTool or PlatformTool, the platform capability adapter builds a canonical `ExecutableStep` and delegates to `StepRunner`.
6. `StepRunner` resolves capability metadata, prepares context/evidence/delay handling, and calls `HarnessInterface.invoke_action(step, context)`.
7. The harness delegates to the active platform tool provider, which invokes the inherited CommonTool or platform-specific PlatformTool implementation.
8. Run events and tool output metadata include safe capability provenance, replay policy when present, sensitivity, safe replay params, status, failure category, and artifact refs.
9. Dynamic recording consumes only replay metadata from successful recordable capability events. AgentTool events are ignored.

### Strict Replay

1. CLI builds the active platform capability registry from the selected platform tool provider only.
2. The registry contains inherited CommonTools and selected-platform PlatformTools; it does not contain AgentTools.
3. FSQ parsing resolves authored aliases such as `waitMs`, `tapOn`, `clickOn`, `assertWithAI`, and platform lifecycle commands through the registry snapshot.
4. Strict replay resolves `runtimeSecret` parameter references in memory at the CLI boundary before external actions begin.
5. `StepSequenceRunner` executes canonical steps through `StepRunner` and the active harness.
6. CommonTool and PlatformTool behavior uses the same implementation path as dynamic execution.

### AI Assertion

`assert_with_ai` is a PlatformTool, not a CommonTool and not an AgentTool.

The exposed decorated method belongs to the concrete backend driver. Android exposes `UiAutomator2AndroidDriver.assert_with_ai`; Web exposes `PlaywrightWebDriver.assert_with_ai`. Both can call a shared AI assertion support component so evaluator invocation, screenshot capture, artifact refs, and result shaping are not duplicated.

The platform tool implementation should:

- Validate Android or Web assert-with-AI parameter models.
- Require an injected provider-backed evaluator.
- Request a fresh screenshot artifact through harness runtime services.
- Build an `AIAssertionRequest` with platform, prompt, screenshot ref/path, UI context, step id, action name, and safe metadata.
- Call the evaluator and normalize its verdict into `HarnessActionResult`.
- Return screenshot and evaluator artifact refs without exposing hidden model reasoning or secret values.

Shared implementation should be extracted into a helper or base component where Android and Web behavior is genuinely identical. Platform differences should remain in parameter model selection, platform id, context shape, screenshot availability, and capability metadata.

## Error Handling And Edge Cases

- AgentTool failures are dynamic helper failures. They should be model-visible as structured tool failures but must not enter replay output.
- CommonTool and PlatformTool failures are execution capability failures. They should flow through `StepRunner` result normalization and evidence/report paths.
- `get_runtime_secret` must preserve current safety behavior: only configured names may be requested, secret values may be visible only to the current model-facing call result when required for task execution, and persisted outputs contain only redacted values and dependency metadata.
- A redacted later platform argument can be bound to a prior runtime-secret dependency only when the recorder can unambiguously identify the requested secret name.
- `wait_ms` remains a pure elapsed-time wait and must not capture platform evidence, alter UI state, or become a synthetic post-action delay.
- PlatformTool provider discovery must not connect to Android devices, import Playwright unnecessarily, launch browsers, or call providers.
- `assert_with_ai` must fail with a clear configuration error when no evaluator is injected.
- Web page-dependent PlatformTools must preserve existing startup-required failures before `start_browser`.
- Harness artifact capture remains the source of screenshot/page-snapshot/ui-tree artifact refs. AgentTool artifact search reads existing text artifacts only and does not decide when platform evidence is produced.

## Compatibility And Migration

The SPEC update should define an explicit migration path because this change crosses public terminology and several internal modules.

Recommended sequence:

1. Introduce AgentTool terminology and dynamic-only adapter behavior while preserving compatibility aliases for current `CommonTool*` names if needed.
2. Introduce a CommonTool mixin or shared provider containing `wait_ms` and `get_runtime_secret`.
3. Introduce Android and Web platform tool providers that inherit CommonTools and expose platform-specific capability definitions.
4. Make `AndroidHarness` and `WebHarness` expose inherited CommonTools plus discovered backend driver capabilities while preserving `HarnessInterface`.
5. Move `assert_with_ai` out of harness classes into concrete backend drivers, backed by a shared visual assertion component used by those drivers.
6. Change dynamic SDK assembly to expose AgentTools plus active platform schemas.
7. Change strict registry bootstrap to include active platform CommonTools and PlatformTools only.
8. Update recorder/report logic terminology so recordability remains `ReplayPolicy`-driven, not name-driven and not AgentTool-driven.
9. Remove compatibility aliases after tests and downstream references are updated, or document them as transitional private APIs.

## Python Architecture Level And Rationale

This remains a Level 3 layered application change for `core` and `agent` because it changes orchestration boundaries among SDK runtime, StepRunner, harness runtime services, platform providers, evidence, and recording metadata.

The new or repurposed AgentTool package should be Level 2 Simple Package: it owns scoped dynamic helper behavior and an SDK adapter, but it should not orchestrate platform execution or strict replay.

The CommonTool mixin/provider and PlatformTool providers live under `core` as part of the Level 3 execution layer because they coordinate platform runtime services, drivers, provider-neutral AI evaluator protocols, evidence artifacts, and runner-facing results. They should not introduce repository, unit-of-work, Clean Architecture, or DDD patterns.

The `capabilities` module remains Level 2: it declares and discovers metadata only. It must not execute AgentTools, CommonTools, PlatformTools, harnesses, drivers, providers, or SDK objects.

## Affected SPEC Changes Expected

Root `SPEC.md` should:

- Replace the old CommonTool terminology with AgentTool/CommonTool/PlatformTool terminology.
- State that AgentTools are dynamic-only and excluded from strict replay registries.
- State that CommonTools are inherited by every platform and are recordable by metadata.
- State that PlatformTools include driver-backed and platform-level recordable capabilities.
- Keep `HarnessInterface.invoke_action` as the stable execution gateway.

`models/SPEC.md` should:

- Update capability metadata terminology.
- Decide whether AgentTool needs separate shared definition/result models or can reuse existing diagnostic tool models under new names.
- Update `CapabilityExecutorKind` or metadata fields if the implementation needs explicit CommonTool/PlatformTool family representation.

`capabilities/SPEC.md` should:

- Add or rename helper decorators to express AgentTool, CommonTool, and PlatformTool declarations.
- Preserve platform-neutral discovery and catalog-backed validation.
- Keep execution out of the declaration module.

`tools/SPEC.md` or a new `agent_tools/SPEC.md` should:

- Own AgentTool provider, registry, adapter, scoped file operations, and bounded artifact retrieval.
- Remove `wait_ms` and `get_runtime_secret` from AgentTool ownership.
- State that AgentTools have no replay policy and are ignored by dynamic recording.

`core/SPEC.md` should:

- Add platform tool provider ownership.
- Add CommonTool mixin/provider ownership for `wait_ms` and `get_runtime_secret`.
- Move `assert_with_ai` ownership from harness classes to concrete backend drivers.
- Clarify that concrete harness classes provide runtime services and route invocation, while `invoke_action` remains long-term.
- Update Android/Web platform blocks and testing contract.

`agent/SPEC.md` should:

- Build SDK tools from AgentTools plus active platform schemas.
- Rename harness tool adapter concepts to platform capability/tool adapter concepts.
- Preserve StepRunner delegation for CommonTools and PlatformTools.

`cli/SPEC.md` and `fsq/SPEC.md` should:

- Build/consume strict registries from active platform CommonTools and PlatformTools only.
- Keep `waitMs` and runtime-secret replay reference behavior.
- Keep dynamic recording driven by replay metadata and ignore AgentTools.

`report/SPEC.md` should:

- Update tool-origin terminology for AgentTool, CommonTool, PlatformTool, and runtime-internal records.

## Open Questions Resolved During Discussion

- `HarnessInterface` is not being removed. It remains the runner-facing runtime interface.
- `HarnessInterface.invoke_action` remains long-term. It is the intended `StepRunner` gateway for invoking active-platform behavior.
- The target removes concrete tool bodies from harness implementations. For example, `AndroidHarness` should not implement `_assert_with_ai`; it should delegate to a platform tool provider.
- CommonTool means platform-default recordable methods, not all SDK-local helper tools.
- AgentTool means dynamic-only SDK helper tools and should not be recorded.
- `assert_with_ai` belongs to backend PlatformTool ownership because it depends on platform screenshot/artifact/runtime context, but its shared logic can be factored to avoid Android/Web duplication.
- CommonTools should be inherited by platform tool providers via mixin/base provider or equivalent composition, not copied into every platform.

## Verification Expectations

The SPEC-driven implementation should include focused tests for:

- AgentTool definitions are exposed to dynamic SDK runtime but excluded from strict capability registries and generated FSQ recordings.
- CommonTool `wait_ms` is inherited by Android and Web platform providers, exposed dynamically, resolved by strict `waitMs`, and recorded through replay metadata.
- CommonTool `get_runtime_secret` is inherited by Android and Web platform providers, enforces allowlists, preserves redaction, and records only dependency metadata.
- Android and Web backend drivers expose existing driver-backed PlatformTools without requiring real device/browser connections during discovery.
- `AndroidHarness.invoke_action` and `WebHarness.invoke_action` route CommonTools to platform providers and backend PlatformTools to concrete drivers while still satisfying `HarnessInterface`.
- `assert_with_ai` execution no longer lives as concrete harness tool body logic and still captures screenshot artifacts, calls injected evaluator, and returns normalized verdict metadata.
- Dynamic recording ignores AgentTool events and records CommonTool/PlatformTool events only from `ReplayPolicy` metadata.
- Strict FSQ parsing resolves active platform aliases and shared `waitMs` without AgentTool registry entries.
- Reports reconstruct tool calls with the new origin terminology and do not expose secret values.

Suggested focused command set after implementation:

```text
./.venv/Scripts/python.exe -m pytest tests/test_capabilities.py tests/test_tools.py tests/test_step_runner.py tests/test_android_harness.py tests/test_web_harness.py tests/test_strict_case_recording.py tests/test_fsq_executable_step_adapter.py tests/test_openai_runtime.py
```

Broader CLI/report/playground tests should run if SPEC implementation touches entry-layer bootstrap, report reconstruction, or playground capability presentation.
