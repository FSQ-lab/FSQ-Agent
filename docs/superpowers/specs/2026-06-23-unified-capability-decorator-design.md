# Unified Capability Decorator Design

Date: 2026-06-23
Status: Ready for user review

## Goal

Introduce one shared capability declaration mechanism for CommonTool, harness-owned, and driver/platform executable capabilities while preserving their different runtime ownership and executor semantics.

The target architecture uses one neutral capability decorator and discovery layer to produce the existing shared `CapabilityDefinition` contract. CommonTool utilities, Android driver methods, future desktop drivers, future web drivers, and harness-owned operations should all declare executable metadata through this shared declaration layer instead of each module inventing a separate decorator implementation.

The design keeps execution routing unchanged at the concept level: `executor_kind="common"` still routes to CommonTool executors, `executor_kind="driver"` still routes through the active harness to a platform driver/backend, and `executor_kind="harness"` still routes to harness-owned handlers such as platform AI assertions. The unification is in declaration and metadata discovery, not in backend execution.

## Scope

This design covers capability declaration, decorator metadata, catalog-backed platform validation, capability discovery helpers, module ownership, public/internal API changes, and the migration path from the current CommonTool and Android driver decorators.

Affected modules:

- New `capabilities` module: owns neutral capability decorators, metadata discovery, platform action catalog helpers, and decorator-time validation shared by `tools` and `core.harness`.
- `models`: continues to own serializable contracts such as `CapabilityDefinition`, `ReplayPolicy`, `CapabilityRegistrySnapshot`, and `CapabilityExecutionResult`. It may gain small catalog contract models only if they must be serialized or shared outside decorator discovery.
- `tools`: uses the neutral decorator layer for CommonTool declarations while keeping CommonTool provider, registry, executor, file/artifact/secret/wait behavior, and SDK adapter ownership.
- `core`: uses the neutral decorator layer for harness/driver declarations while keeping `CapabilityRegistry`, `CapabilityExecutorBindings`, `StepRunner`, harness protocols, platform harnesses, and evidence coordination ownership.
- `agent`, `cli`, `fsq`, `report`, and `playground`: should continue to consume validated capability definitions, registry snapshots, and normalized runner results. They should not import decorator internals.

## Non-Goals

This design does not implement code and does not update root or module `SPEC.md` files. The next SDD step is to translate this confirmed design into SPEC updates, get SPEC confirmation, then implement.

This design does not merge CommonTool execution with harness or driver execution. It does not move CommonTool providers into `core`, does not move harness implementations into `tools`, and does not make `StepRunner` depend on decorator implementation details.

This design does not add new web, desktop, iOS, or additional Android capabilities. It only creates the declaration architecture that makes those future platforms cheaper and less repetitive.

This design does not require preserving the current private decorator names as long-term APIs. Compatibility aliases may be kept temporarily where they reduce churn, but the target public/internal names should express the new architecture.

## Selected Approach

Create a new neutral `fsq_agent.capabilities` package above `models` and below feature modules.

Dependency direction:

```text
models
  ↑
capabilities
  ↑        ↑
core      tools
  ↑        ↑
cli/agent/playground/root bootstrap
```

Rules:

- `capabilities` may import public symbols from `models` and standard library helpers.
- `capabilities` must not import `core`, `tools`, `agent`, `cli`, `fsq`, `providers`, `report`, `playground`, or SDK/backend runtime types.
- `tools` may import `capabilities` and `models`.
- `core` may import `capabilities` and `models` after root SPEC updates explicitly allow this dependency.
- `core` still must not import `tools`; `tools` still must not import `core`.
- Entry-layer private bootstrap at `fsq_agent._capability_bootstrap` remains responsible for composing CommonTool definitions, platform definitions, registries, executor bindings, and configured runtime providers.

The new module provides one underlying `@capability(...)` decorator plus thin domain helpers for readability and validation. Code may use the neutral decorator directly for simple declarations, but most call sites should use domain helpers such as `common_capability(...)` or `platform_driver_capability(...)` so declarations remain self-documenting.

## Target Module Ownership

### `models`

`models` remains the contract layer. It owns serializable Pydantic models and project exceptions. It should not own reflection, decorator attributes, callable discovery, or platform-specific validation logic.

`CapabilityDefinition` remains the authoritative serializable executable metadata contract. Runtime callables, SDK tool objects, driver instances, and decorator marker objects must not be stored in `CapabilityDefinition`.

If a platform action catalog must be serializable across modules, `models` may own a small contract such as `CapabilityActionDefinition`. Otherwise, catalog helper dataclasses should live in `capabilities` to keep `models` from becoming a behavior module.

### `capabilities`

`capabilities` owns declaration mechanics:

- The neutral `capability(...)` decorator.
- Thin helper decorators such as `common_capability(...)`, `driver_capability(...)`, `harness_capability(...)`, and `platform_driver_capability(...)`.
- Marker attribute names used to attach metadata to Python functions.
- Discovery helpers that read decorated class/object methods and return `CapabilityDefinition` values.
- Catalog-backed validation for platform action declarations.
- Optional conversion helpers from catalog entries to capability definitions.

`capabilities` must not own execution. It does not invoke CommonTools, drivers, harnesses, providers, or SDK tools.

### `tools`

`tools` owns CommonTool behavior and SDK-neutral CommonTool execution:

- CommonTool providers and provider registry.
- CommonTool executor.
- File, artifact, runtime-secret, and wait implementations.
- CommonTool result normalization before `StepRunner` wraps results.
- OpenAI Agents SDK CommonTool adapter.

The existing CommonTool decorator implementation should move out of `tools` into `capabilities`. `tools` may re-export `common_capability` or a compatibility alias if its SPEC chooses to keep a public decorator surface for CommonTool authors.

### `core`

`core` owns execution orchestration and platform harness behavior:

- `CapabilityRegistry` and `CapabilityExecutorBindings`.
- `StepRunner` and `StepSequenceRunner`.
- Harness protocols and concrete platform harnesses.
- Driver interfaces and concrete backend drivers.
- Evidence capture and artifact coordination.

The current Android-specific `_android_driver_tool` helper should be replaced by a catalog-backed `platform_driver_capability(...)` helper from `capabilities`. Android remains one catalog consumer rather than a unique decorator implementation.

`core` must not import `tools`, and `tools` must not import `core`. Both modules may import `capabilities` after root SPEC updates add the module and its allowed dependency edges.

## Decorator API

The low-level decorator should produce one internal decorated metadata record that can be discovered and converted into a `CapabilityDefinition`.

Target shape:

```python
def capability(
    *,
    name: str | None = None,
    aliases: list[str] | None = None,
    executor_kind: CapabilityExecutorKind,
    owner: str | None = None,
    params_model: type[BaseModel] | None = None,
    description: str = "",
    platform: HarnessPlatform | None = None,
    backend: str | None = None,
    step_kind: ExecutableStepKind = "action",
    capture_evidence: bool = False,
    sensitivity: bool = False,
    replay: ReplayPolicy | None = None,
    strict: bool = True,
    metadata: dict[str, Any] | None = None,
    action_catalog: CapabilityActionCatalog | None = None,
    action_name: str | None = None,
) -> Callable[[F], F]:
    ...
```

The neutral decorator must validate legal combinations enough to catch declaration bugs early:

- `executor_kind="common"` should not require platform catalog information.
- `executor_kind="driver"` should either declare explicit `params_model` and metadata or use a catalog entry that supplies them.
- `executor_kind="harness"` may declare platform/backend metadata without requiring a driver method.
- `sensitivity=True` is legal for CommonTool and harness capabilities but requires result redaction behavior during execution.
- `capture_evidence=True` is meaningful for harness/driver/platform actions and should not accidentally trigger platform evidence for pure CommonTool utilities unless a future SPEC records that intent.

## Thin Domain Helpers

The target API should avoid forcing every call site to use a large generic decorator directly.

CommonTool declarations can use:

```python
@common_capability(
    name="wait_ms",
    aliases=["waitMs"],
    params_model=WaitMsParams,
    description="Wait without touching platform state.",
    replay=ReplayPolicy(kind="fsq_command", alias="waitMs"),
)
async def _wait_ms(...):
    ...
```

Driver declarations can use:

```python
android_driver_capability = platform_driver_capability(
    platform="android",
    backend="uiautomator2",
    catalog=ANDROID_ACTION_CATALOG,
)

@android_driver_capability(
    "tapOn",
    description="Tap an Android UI target.",
    capture_evidence=True,
)
def tap_on(self, params: AndroidTapOnParams):
    ...
```

Harness-owned declarations can use:

```python
@harness_capability(
    name="assert_with_ai",
    aliases=["assertWithAI"],
    params_model=AndroidAssertWithAIParams,
    platform="android",
    owner="harness",
    step_kind="assertion",
    replay=ReplayPolicy(kind="fsq_command", alias="assertWithAI"),
)
def assert_with_ai(...):
    ...
```

These helpers are wrappers around the same low-level decorator and produce the same discoverable metadata format.

## Platform Action Catalog

The Android-specific intent currently embedded in `_android_driver_tool` should become catalog-backed validation.

A platform action catalog entry should describe:

- Authored action name, such as `tapOn`.
- Canonical capability name, such as `tap_on`.
- Expected owner, such as `driver` or `harness`.
- Expected executor kind, such as `driver`.
- Expected method name when the capability is bound to a backend method.
- Parameter model.
- Step kind.
- Replay alias and replay kind.
- Default evidence policy.
- Optional platform/backend provenance defaults.

Example shape:

```python
@dataclass(frozen=True)
class CapabilityActionDefinition:
    action_name: str
    canonical_name: str
    executor_kind: CapabilityExecutorKind
    owner: str
    params_model: type[BaseModel]
    step_kind: ExecutableStepKind = "action"
    method_name: str | None = None
    replay: ReplayPolicy | None = None
    capture_evidence: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
```

Future desktop and web platforms should add catalog entries, not new decorator implementations.

```python
web_driver_capability = platform_driver_capability(
    platform="web",
    backend="playwright",
    catalog=WEB_ACTION_CATALOG,
)

desktop_driver_capability = platform_driver_capability(
    platform="desktop",
    backend="winappdriver",
    catalog=DESKTOP_ACTION_CATALOG,
)
```

## Discovery Helpers

The current project has separate discovery mechanisms for CommonTool declarations and driver declarations. The target design should centralize the reflection layer:

```python
discover_capability_definitions(
    target: object,
    *,
    metadata: dict[str, object] | None = None,
) -> list[CapabilityDefinition]
```

Rules:

- `target` may be a class or instance.
- Discovery must inspect decorated methods without invoking them.
- Discovery must not connect to a backend, instantiate SDK tools, or call providers.
- Discovery applies metadata defaults, resolves catalog entries, infers parameter models only when safe and explicit enough, and returns serializable `CapabilityDefinition` values.
- Duplicate/ambiguous name validation remains owned by `core.CapabilityRegistry`, not by discovery.

`DefaultCommonToolProvider.capability_definitions()` should call this shared helper.

`android_capability_definitions()` should call the same helper against `UiAutomator2AndroidDriver` plus Android catalog defaults, then append or discover harness-owned `assert_with_ai` according to the SPEC-confirmed platform design.

## Public API Expectations

The new `capabilities` module should export only declaration-layer APIs:

- `capability`
- `common_capability`
- `driver_capability`
- `harness_capability`
- `platform_driver_capability`
- `CapabilityActionDefinition` or equivalent catalog entry type if it is not placed in `models`
- `CapabilityActionCatalog` or a simple mapping type alias
- `discover_capability_definitions`

`tools.__init__` may export `common_capability` or retain `capability` as a compatibility alias only if the module SPEC explicitly says CommonTool authors should import decorators from `tools`. The preferred long-term import is from `fsq_agent.capabilities`.

`core.harness.__init__` may export `platform_driver_capability` or an Android-bound helper only if the module SPEC records it as part of the harness extension API. Private platform modules may import directly from `capabilities`.

## Migration Plan

1. Add `fsq_agent/capabilities` with neutral decorator, domain helper decorators, catalog helper contracts, and discovery helper tests.
2. Update root `SPEC.md` module table and architecture diagram to include `capabilities`, with allowed imports from `core` and `tools` to `capabilities`.
3. Update `models`, `tools`, `core`, and relevant agent/cli/fsq/report/playground specs to reflect the new declaration layer and unchanged runtime routing.
4. Move CommonTool decorator metadata attachment from `tools._common` to `capabilities` while keeping CommonTool execution behavior in `tools`.
5. Replace `_android_driver_tool` with a catalog-backed platform driver helper. Keep `driver_tool` only if it remains useful as a thin compatibility wrapper around `capability(...)`; otherwise remove it from public exports after SPEC confirmation.
6. Update Android default capability discovery to call shared discovery helpers.
7. Keep `CapabilityRegistry`, `CapabilityExecutorBindings`, `StepRunner`, SDK adapters, strict FSQ parsing, recording, and reporting behavior consuming `CapabilityDefinition` without caring which decorator helper produced it.
8. Update tests for CommonTool declaration discovery, platform catalog validation, module import boundaries, and unchanged dynamic/strict execution behavior.

## Error Handling And Validation

Declaration and discovery should fail fast with `ConfigurationError` when:

- A catalog action name is unknown.
- A catalog entry owner or executor kind is incompatible with the helper used.
- A decorated method name does not match a catalog-required method name.
- A method annotation supplies a different parameter model from the catalog entry.
- No parameter model can be resolved.
- An invalid executor kind/owner/platform combination is declared.
- A decorator tries to store non-serializable runtime objects in capability metadata.

Registry-level failures remain in `core.CapabilityRegistry`:

- Duplicate canonical names.
- Alias conflicts.
- Ambiguous aliases.
- Missing executor bindings for a selected entry mode.

Runtime failures remain in their owning executors and `StepRunner`:

- CommonTool invocation errors.
- Harness/driver target misses and backend exceptions.
- Evidence capture failures.
- Sensitive output shape violations.

## Verification Expectations

Focused verification should include:

- New unit tests for neutral decorator metadata and discovery.
- New tests that CommonTool declarations still produce the same `CapabilityDefinition` values for `wait_ms` and `get_runtime_secret`.
- New tests that Android catalog-backed declarations validate method names and parameter models.
- Existing tests for `CapabilityRegistry`, `StepRunner`, `AgentsCommonToolAdapter`, FSQ executable step adaptation, strict replay, Android harness dispatch, and dynamic runtime startup.

Expected command set after implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_tools.py tests/test_android_harness.py tests/test_step_runner.py tests/test_fsq_executable_step_adapter.py tests/test_strict_replay.py tests/test_openai_runtime.py
```

A broader repository pytest run should be attempted after focused tests. Known unrelated failures should be reported separately and must not be hidden.

## Python Architecture Level

This change keeps the repository at the existing architecture levels:

- New `capabilities`: Level 2 Simple Package. It owns reusable declaration helpers and validation but no orchestration, persistence, providers, SDK runtime, or backend execution.
- `tools`: Level 2 Simple Package. It keeps focused CommonTool behavior and SDK-neutral execution.
- `core`: Level 3 Layered Application. It keeps execution routing, harness coordination, and evidence orchestration.
- `agent` and `cli`: Level 3 Layered Application. They keep runtime/entry orchestration and consume the registry, not decorator internals.

No Repository, Unit of Work, Clean Architecture, or DDD patterns are justified by this change.

## Benefits

- One metadata declaration mechanism for CommonTool, harness, and driver capabilities.
- Future web, desktop, and iOS harness platforms can add catalogs instead of copying Android-specific decorator logic.
- Catalog-backed validation catches platform declaration bugs close to the method being decorated.
- `CapabilityDefinition` remains the shared runtime contract consumed by parsers, adapters, runners, recorders, and reports.
- Module boundaries stay explicit: declaration mechanics live in `capabilities`, execution remains in `tools` and `core`.
- Tests can exercise declaration semantics once instead of repeating decorator behavior per platform.

## Costs And Risks

- A single low-level decorator can become parameter-heavy if domain helpers are not used consistently.
- Introducing a new module changes the project DAG and requires careful SPEC updates before implementation.
- Existing tests that import `tools.capability` or `core.harness.driver_tool` may need migration or compatibility aliases.
- Catalog design must avoid duplicating `CapabilityDefinition` too heavily; catalog entries should describe authored platform action facts, while `CapabilityDefinition` remains runtime metadata.
- If `capabilities` accidentally imports execution modules, it would create cycles and undo the boundary benefit.
- Over-validating decorator combinations could make legitimate future capabilities awkward; validation should catch clear contradictions while leaving room for SPEC-confirmed extensions.

## Resolved Decisions

- Use one neutral declaration mechanism, not one unified executor.
- Keep CommonTool and harness/driver runtime ownership separate.
- Introduce a new `capabilities` module instead of putting decorator behavior in `models`, `tools`, or `core.harness`.
- Keep `models` focused on serializable contracts.
- Generalize `_android_driver_tool` into catalog-backed platform driver declaration so future desktop/web platforms reuse the same logic.
- Keep root bootstrap as the composition point for default registry and executor bindings.

## Affected Specs Expected To Change

- Root `SPEC.md`: add `capabilities` module, DAG edges, development rules for declaration/execution separation, and updated decorated capability execution language.
- `fsq_agent/models/SPEC.md`: clarify that models own contracts only and do not own decorator discovery.
- New `fsq_agent/capabilities/SPEC.md`: define purpose, dependencies, public interface, internal structure, architecture level, validation, tests, and design decisions.
- `fsq_agent/tools/SPEC.md`: replace ownership of the decorator implementation with use of `capabilities`; keep CommonTool behavior ownership.
- `fsq_agent/core/SPEC.md`: allow import of `capabilities`, replace Android-specific decorator language with catalog-backed platform driver declarations, and keep runtime orchestration ownership.
- `fsq_agent/agent/SPEC.md`: clarify that SDK tools consume registry definitions and do not import decorator internals.
- `fsq_agent/cli/SPEC.md`, `fsq_agent/fsq/SPEC.md`, `fsq_agent/report/SPEC.md`, and `fsq_agent/playground/SPEC.md`: confirm they consume registry metadata and normalized runner results rather than decorator internals.
