# Driver Action Space Function Schema Design

## Goal

`HarnessInterface.action_space()` should expose complete, OpenAI-compatible function schemas for platform driver methods. The schema source of truth for each driver method parameter payload should be a concrete Pydantic model, so FSQ YAML parsing, future FSQ YAML generation, harness dispatch validation, and function-call schema generation all share the same payload contract.

## Scope

This design covers the schema and validation contract for the existing Android strict-core driver path.

- `fsq_agent.models` owns shared Android driver parameter Pydantic models and serializable function-schema models.
- `fsq_agent.core.harness` owns concrete driver method decorators, schema discovery helpers, and the updated `HarnessInterface.action_space()` contract.
- `AndroidDriverInterface`, `AndroidHarness`, and `UiAutomator2AndroidDriver` move driver method parameters from raw dictionaries to typed Pydantic parameter models.
- `fsq_agent.fsq` validates and normalizes Android FSQ command payloads through the shared parameter models when producing `ExecutableStep.params`.
- Future case YAML generation should use the same parameter models through canonical `model_dump(mode="json", exclude_none=True)` output.

## Non-Goals

- Do not construct OpenAI Agents SDK `FunctionTool` objects in `core` or `harness`.
- Do not expose undecorated concrete driver methods through `action_space()`.
- Do not add a complete `.codex.yaml` case generation API in this cycle.
- Do not implement unsupported Android DSL commands as part of this schema work.
- Do not change strict execution, retry, recovery, AI locator fallback, evidence policy, or report aggregation behavior.

## Proposed Design

### Schema Ownership

The model-facing function schema is owned at the concrete driver method layer. Tool names should use driver method names such as `tap_on`, `input_text`, and `assert_visible`, not FSQ action names such as `tapOn` or `inputText`.

The Android harness should keep FSQ action mapping metadata so strict FSQ execution can still dispatch authored action names to driver methods and record understandable provenance. That mapping is not the function-call tool naming surface.

### Concrete Driver Decorator

Concrete driver methods opt in to action-space schema discovery with a metadata decorator. Conceptually:

```python
@driver_tool(description="Tap an Android UI target.")
def tap_on(self, params: AndroidTapOnParams) -> dict[str, object]:
    ...
```

The decorator applies only to concrete implementations such as `UiAutomator2AndroidDriver`. `AndroidDriverInterface` describes the callable shape, but it is not the schema registration source. This keeps the registration behavior explicit per backend and prevents an interface method from exposing a tool that a concrete backend has not intentionally enabled.

The decorator should:

- Store metadata on the method without wrapping or changing method behavior.
- Infer the Pydantic parameter model from the method annotation when possible.
- Allow an explicit `params_model=` override when annotation inference is ambiguous.
- Carry a model-facing description.
- Optionally carry FSQ provenance metadata such as `fsq_action_name="tapOn"`.
- Avoid importing or depending on the OpenAI Agents SDK.

Discovery should walk `type(driver)` and include only decorated callable methods. Stub methods and unsupported backend operations should not appear unless a concrete implementation explicitly decorates them.

### Action Space Return Shape

`HarnessInterface.action_space()` should return pure serializable schema definitions using a shared `HarnessFunctionSchema` model. The shape should include:

- `name`: driver method name, for example `tap_on`.
- `description`: decorator-provided model-facing description.
- `params_json_schema`: strict JSON schema derived from the Pydantic parameter model.
- `strict`: `True` by default.
- `platform`: platform value such as `android`.
- `driver_method`: the Python method name used for dispatch.
- `fsq_action_name`: optional FSQ action name mapped to the driver method.
- `metadata`: backend details such as `backend="uiautomator2"`.

The returned schema must be directly usable by an adapter that creates OpenAI Agents SDK function tools later. That adapter belongs in `tools` or `agent`, not in `core`.

### Android Parameter Models

Shared Android parameter models should live in `fsq_agent.models`, because both `fsq` and `core` depend on `models`, while `fsq` must not import `core`.

The first Android model set should cover the current phase-1 strict Android actions only:

- `AndroidLocator`: optional locator fields `resourceId`, `accessibilityId`, `text`, `className`, and `xpath`.
- Target-bearing parameter models for `tap_on`, `long_press_on`, `assert_visible`, `assert_not_visible`, and `input_text`.
- `AndroidInputTextParams` with required `text` plus target or locator fields.
- `AndroidPressKeyParams` with a required normalized key value.
- `AndroidSwipeParams` with direction form or point form, validated by Pydantic.
- `AndroidPoint` for swipe coordinates.
- `AndroidAssertStateParams` with text assertion and Android element-state assertion shapes.
- `AndroidAssertWithAIParams` for harness-owned visual assertion validation.
- Lifecycle parameter models with explicit fields only, such as optional `app_id`.

All parameter models should forbid unexpected fields unless a field is intentionally modeled. This keeps function-call schemas strict and prevents silent acceptance of payload shapes that neither FSQ parsing nor driver execution understands.

Runner-owned metadata remains outside driver parameter models. Examples include `timeout_ms`, evidence policy, source references, retry policy, and step identifiers. FSQ adapter logic may extract metadata before validating the driver payload and storing the canonical payload dict in `ExecutableStep.params`.

### FSQ YAML Flow

`FsqExecutableStepAdapter` should validate known Android command payloads through the shared Pydantic models when converting FSQ cases into `ExecutableStep` records.

For each known action:

1. Parse the authored YAML command into an action name and raw payload using existing command-shape rules.
2. Require known Android command payloads to use the same object field names as their parameter models, such as `pressKey: {key: Enter}` and `tapOn: {target: Login}`.
3. Validate with the shared parameter model for that FSQ action.
4. Store `model_dump(mode="json", exclude_none=True)` in `ExecutableStep.params`.
5. Store runner-owned metadata, such as valid timeout values, in the existing `ExecutableStep` fields rather than passing them to driver methods.

The FSQ adapter and Android harness should use one shared Android action registry from `models` for FSQ action name, driver method name, parameter model, and deterministic step kind. Concrete driver decorators should also be backed by that registry so method names and parameter annotations cannot drift from strict dispatch. The FSQ adapter should not use concrete driver decorators as its registry, because YAML parsing must remain backend-neutral and happens before a concrete driver instance necessarily exists.

### Harness Dispatch Flow

`AndroidHarness.invoke_action()` should continue dispatching strict FSQ actions by authored FSQ action name. Before calling the concrete driver method, it should validate `ExecutableStep.params` with the same parameter model associated with the target driver method.

After validation, the harness calls the driver with a typed Pydantic model instance:

```python
result = driver.tap_on(AndroidTapOnParams.model_validate(step.params))
```

The concrete driver should read fields from the typed model instead of indexing raw dictionaries. Driver output remains a dictionary for now so existing `HarnessActionResult` conversion behavior can stay focused and compatible.

### Function-Call Flow

`AndroidHarness.action_space()` should ask the concrete driver schema-discovery helper for decorated method definitions and return those definitions as serializable schemas. The OpenAI Agents SDK runtime can later adapt each definition into a `FunctionTool` by passing the schema's `params_json_schema` field as the SDK `params_json_schema` argument.

This design intentionally keeps `action_space()` as a capability description. It does not make the strict StepRunner execute model-generated function calls directly in this cycle.

## Error Handling

- Pydantic validation failures from FSQ adapter normalization should raise `ConfigurationError` with case path and step index context before execution starts.
- Pydantic validation failures during harness dispatch should return `HarnessActionResult(status="failed", failure_category="configuration_error")` before any driver side effect.
- Driver execution failures keep existing categories such as `target_resolution_error`, `assertion_error`, `action_error`, and `configuration_error`.
- Missing decorator metadata means the method is absent from `action_space()`; it is not a runtime execution failure by itself.
- Schema discovery failures, such as a decorated method with no resolvable Pydantic parameter model, should be configuration errors surfaced during `action_space()` discovery.

## Affected SPEC Files Expected To Change

- `fsq_agent/models/SPEC.md`: add shared Android driver parameter models and serializable function-schema model expectations.
- `fsq_agent/core/SPEC.md`: update `HarnessInterface.action_space()`, decorator discovery, Android harness validation, and typed Android driver method signatures.
- `fsq_agent/fsq/SPEC.md`: update deterministic step adapter behavior to validate and dump Android payloads through shared Pydantic models.
- Root `SPEC.md`: only needs a small update if the project-level module summary should mention action-space schemas explicitly.
- `fsq_agent/tools/SPEC.md`: no change is required for this design unless the next implementation cycle also adapts action-space schemas into SDK `FunctionTool` objects.

## Open Questions Resolved

- Function schemas should be exposed at the driver method layer, not the FSQ action layer.
- Registration should be decorator-based on concrete driver classes only.
- `action_space()` should return pure serializable JSON/function schema definitions, not OpenAI Agents SDK objects.
- This design should unify parameter models and dump shapes for parsing, future generation, and function calling, but should not add a full case YAML generator.
- Validation failures should happen before driver side effects and map to configuration errors.

## Verification Expectations

- Unit tests for every new Android parameter model, including valid canonical dumps and invalid extra-field rejection.
- Unit tests proving decorated `UiAutomator2AndroidDriver` methods appear in `AndroidHarness.action_space()` with strict JSON schemas.
- Unit tests proving undecorated methods do not appear in `action_space()`.
- Unit tests proving malformed FSQ payloads fail during FSQ adapter validation with useful configuration context.
- Unit tests proving malformed harness dispatch payloads fail before a fake driver method is called.
- Regression tests proving existing strict Android FSQ steps still dispatch from FSQ action names to concrete driver methods.
- A SPEC implementation audit after implementation, comparing the final diff to confirmed root/module SPEC updates.

## Handoff

After this design is reviewed and approved, the next step is to use `spec-driven` to update the relevant root and module `SPEC.md` files from this document. Implementation should start only after those SPEC changes are confirmed.
