# Module: capabilities

## Purpose

Own the neutral capability declaration layer for fsq-agent. This module provides shared decorators, thin domain helper decorators, platform action catalog contracts, catalog-backed validation, and decorated-method discovery helpers that produce serializable `CapabilityDefinition` records for CommonTool, harness-owned, and driver/platform capabilities.

This module does not execute capabilities, invoke CommonTool providers, call harnesses or drivers, construct SDK tools, parse FSQ YAML, build registries, or generate reports. Execution ownership remains in `tools`, `core`, `agent`, `cli`, and entry-layer bootstrap code.

## Dependencies

- Internal project dependencies: `models` only. Uses `CapabilityDefinition`, `CapabilityExecutorKind`, `ExecutableStepKind`, `HarnessPlatform`, `ReplayPolicy`, and `ConfigurationError`.
- External dependencies: standard library dataclasses, inspect, typing, and Pydantic `BaseModel` type references.
- Forbidden dependencies: `core`, `tools`, `agent`, `cli`, `fsq`, `config`, `providers`, `report`, `playground`, `observation`, `knowledge`, `skills`, OpenAI Agents SDK types, concrete driver/runtime objects, and backend SDKs.

## Public Interface

Target `__init__.py` exports via `__all__`:

- `CapabilityActionDefinition`: Lightweight catalog entry for authored platform actions. It describes authored action name, canonical capability name, executor kind, owner, parameter model, optional required method name, step kind, replay policy, default evidence policy, optional post-action delay override, and safe metadata defaults.
- `CapabilityActionCatalog`: Mapping type alias from authored action name to `CapabilityActionDefinition`.
- `capability`: Neutral low-level decorator that attaches capability declaration metadata to a function or method. It can declare common, harness, or driver capabilities, but it does not register or execute them.
- `common_capability`: Thin helper around `capability` for `executor_kind="common"` declarations owned by `tools`.
- `driver_capability`: Thin helper around `capability` for explicit driver declarations that do not need a platform action catalog.
- `harness_capability`: Thin helper around `capability` for harness-owned capabilities such as platform AI assertions.
- `platform_driver_capability`: Factory that binds a platform/backend/catalog and returns a decorator for catalog-backed driver method declarations.
- `discover_capability_definitions(target: object, *, metadata: dict[str, object] | None = None) -> list[CapabilityDefinition]`: Inspect a decorated class or instance without invoking methods and return serializable capability definitions.

The neutral decorator API accepts canonical name, aliases, executor kind, owner, parameter model, description, platform, backend, step kind, evidence flag, optional post-action delay override, sensitivity flag, replay policy, strict schema flag, safe metadata, and optional catalog/action name inputs. `post_action_delay_seconds=None` means inherit the configured executor-kind default; `0` explicitly disables runner-owned post-action delay for that capability; positive values override the configured default. Domain helpers should be preferred at call sites so CommonTool and platform-driver declarations remain readable.

## Internal Structure

- `__init__.py`: Public exports only.
- `_decorators.py`: Neutral decorator, domain helper decorators, marker metadata, and legal-combination validation.
- `_catalog.py`: `CapabilityActionDefinition`, catalog mapping type, catalog lookup, and catalog-to-capability defaults.
- `_discovery.py`: Reflection helpers that discover decorated methods on classes or instances and convert metadata into `CapabilityDefinition` values.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: declaration decorators, catalog entry types, and discovery helpers exported from `__init__.py`.
- Internal modules: `_decorators.py`, `_catalog.py`, and `_discovery.py` are private implementation modules.
- Domain boundaries: this module owns declaration metadata and validation only. CommonTool safety and invocation live in `tools`; runner routing, harness/driver dispatch, and evidence live in `core`; SDK adapters live in `agent` and `tools`; strict FSQ parsing lives in `fsq` and entry modules.
- Boundary models: serializable capability contracts come from `models`. Decorator marker objects and catalog helper dataclasses are not persisted as runtime results.
- Dependency direction: imports public `models` only; may be imported by `tools` and `core`; must not import any execution or entry-layer module.
- Rationale: the module is a focused reusable declaration utility with validation and reflection only, so Level 2 is sufficient and a higher architecture level would add ceremony without isolating additional side effects.

## Error Handling

Declaration and discovery fail fast with `ConfigurationError` when a decorated capability is inconsistent or unsafe to expose:

- Missing or unresolvable parameter model.
- Unknown catalog action name.
- Catalog entry owner or executor kind incompatible with the selected helper.
- Decorated method name does not match a catalog-required method name.
- Method annotation conflicts with the catalog or explicit parameter model.
- Invalid executor kind, owner, platform, backend, sensitivity, or evidence combination.
- Negative post-action delay values in decorator arguments or catalog entries.
- Capability metadata attempts to store non-serializable runtime objects.

Duplicate capability names, alias conflicts, ambiguous aliases, and missing executor bindings remain registry/bootstrap concerns owned by `core` and entry-layer code.

## Testing Contract

- Unit tests: neutral decorator metadata, domain helper defaults, post-action delay override validation, catalog lookup/validation, method-name and parameter-model validation, discovery from class and instance targets, safe metadata merging, and no method invocation during discovery.
- Regression tests: `common_capability` produces the same `CapabilityDefinition` shape expected by CommonTool registry/bootstrap; catalog-backed Android declarations produce the same canonical names, aliases, parameter models, replay metadata, owner, platform/backend, evidence flags, and post-action delay overrides as the previous Android-specific helper plus the new delay contract.
- Boundary tests: `capabilities` imports only `models` among project modules and has no dependency on `core`, `tools`, SDK objects, or concrete backend libraries.
- Verification commands: `./.venv/Scripts/python.exe -m pytest tests/test_capabilities.py tests/test_tools.py tests/test_android_harness.py` plus broader capability/runner tests when implementations change.

## Design Decisions

- One declaration mechanism prevents CommonTool, Android, future web, future desktop, and future iOS capabilities from growing separate decorator semantics.
- Domain helper decorators are intentionally thin wrappers around the neutral decorator. They preserve readability while keeping one metadata format.
- Platform differences belong in action catalogs, not in per-platform decorator implementations. Future platforms should add catalogs and reuse `platform_driver_capability`.
- `CapabilityDefinition` remains the runtime contract and registry input. Decorators attach declaration metadata to functions, including optional post-action delay overrides; discovery converts that metadata into serializable definitions.
- Discovery must be side-effect free. It may inspect method signatures and type hints, but it must not call methods, connect to devices, instantiate SDK tools, or build providers.
- Runtime routing is out of scope. `executor_kind` is metadata consumed by `core.StepRunner` and executor bindings; `capabilities` never invokes the selected executor.
- `models` stays contract-only. Keeping decorator behavior out of `models` avoids turning the shared schema module into a reflection/behavior layer.
