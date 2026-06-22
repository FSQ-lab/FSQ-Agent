# Driver Tool Evidence Flag Design

Date: 2026-06-22
Status: Confirmed design

## Goal

Optimize the dynamic harness evidence capture implementation introduced by merge `08bec7187d591ace173fdf99d22b1b00da998fe0` by moving the list of Android driver tools that need dynamic before/after evidence out of `HarnessToolAdapter` and into the driver tool declaration point.

The intended behavior does not change: dynamic harness calls for reviewed UI-changing Android tools still execute through `StepRunner` and capture before/after screenshot and UI tree artifacts. The ownership of the reviewed evidence-capture flag changes so method-level tool management stays with the method declaration.

## Scope

This design covers the Android driver tool schema path:

- `@_android_driver_tool(...)` declarations on concrete Android driver methods.
- `driver_tool(...)` and `_DriverToolMetadata` in `core/harness/_driver_tools.py`.
- `HarnessFunctionSchema` in `models/_core.py`.
- `HarnessToolAdapter` in `agent/_harness_tools.py`.

The design applies to dynamic LLM runs that invoke harness platform tools through `HarnessToolAdapter`. Strict-core execution remains unchanged.

## Non-Goals

Do not change the dynamic execution path selected by the previous design. Dynamic harness tools still execute through:

```text
OpenAI Agents SDK -> HarnessToolAdapter -> StepRunner -> harness.invoke_action()
```

Do not add YAML configuration for evidence capture.

Do not expose currently unexposed Android driver methods only to carry an evidence flag. In particular, the current uiautomator2 `perform_actions` method is not decorated as a dynamic tool and should not become exposed as part of this optimization.

Do not add generic before/after evidence to assertion or observation tools such as `assertVisible`, `assertNotVisible`, `assert`, `assertWithAI`, or `uiTree`.

Do not replace the existing dynamic tool output contract or upgrade dynamic reports to strict-core evidence bundles in this change.

## Proposed Design

### Selected Approach

Add a typed `capture_evidence` flag to the driver tool schema pipeline.

`_android_driver_tool(...)` should accept a keyword-only parameter:

```python
capture_evidence: bool = False
```

The parameter should flow through the generic driver tool metadata path and become an explicit `HarnessFunctionSchema.capture_evidence` field. `HarnessToolAdapter` should then derive dynamic evidence policy from `schema.capture_evidence` instead of maintaining a private `_UI_MUTATING_ACTIONS` allowlist.

This keeps method-level action exposure and method-level evidence capture intent together while avoiding a second action list in the agent adapter.

### Runtime Data Flow

1. A concrete Android driver method declares evidence capture intent at the method declaration point:

   ```python
   @_android_driver_tool("tapOn", description="Tap an Android UI target.", capture_evidence=True)
   ```

2. `_android_driver_tool(...)` continues to validate the FSQ action name against `ANDROID_ACTION_DEFINITIONS_BY_NAME`, including driver method name, parameter model, and driver ownership.

3. `_android_driver_tool(...)` passes `capture_evidence` into `driver_tool(...)`.

4. `_DriverToolMetadata` stores `capture_evidence` alongside description, parameter model, FSQ action name, strictness, and metadata.

5. `_discover_driver_function_schemas(...)` copies the flag into `HarnessFunctionSchema.capture_evidence`.

6. `OpenAIAgentsRuntime` builds harness tools as it does today.

7. When a dynamic harness tool is invoked, `HarnessToolAdapter` builds an `ExecutableStep` and applies the standard dynamic evidence policy when `schema.capture_evidence is True`:

   ```python
   EvidencePolicy(
       capture_before=True,
       capture_after=True,
       capture_on_failure=True,
       artifact_kinds=["screenshot", "ui_tree"],
   )
   ```

8. `HarnessToolAdapter` calls `StepRunner.run_step(...)`, preserving the previous merge's runner-owned prepare, invoke, finalize, and artifact capture behavior.

### Tool Classification

The following currently exposed uiautomator2 driver tools should set `capture_evidence=True`:

- `launchApp`
- `killApp`
- `tapOn`
- `longPressOn`
- `inputText`
- `pressKey`
- `swipe`

The following currently exposed tools should keep the default `capture_evidence=False`:

- `assertVisible`
- `assertNotVisible`
- `assert`
- `uiTree`

`assertWithAI` is harness-owned rather than declared with `_android_driver_tool(...)`; it should keep the default behavior. It captures its assertion screenshot during invoke and should not receive generic before/after evidence.

`performActions` was present in the old adapter allowlist but is not currently decorated as a uiautomator2 dynamic tool. This design should not expose it. If a backend later exposes `performActions` with `_android_driver_tool(...)`, that backend should declare `capture_evidence=True` at that method.

### Alternatives Considered

#### Keep `_UI_MUTATING_ACTIONS` In `HarnessToolAdapter`

This is the smallest code change but leaves a second hand-maintained action list in the agent adapter. It conflicts with the goal of managing method behavior near method registration.

#### Add A Flag To `AndroidActionDefinition`

This keeps Android action facts centralized in `ANDROID_ACTION_DEFINITIONS`, but it applies at the FSQ action contract level rather than the concrete driver tool declaration level. It also does not match the desired control point at `_android_driver_tool(...)`.

#### Store The Flag Only In `HarnessFunctionSchema.metadata`

This avoids adding a model field, but the agent changes execution behavior based on the flag. A typed `HarnessFunctionSchema.capture_evidence` field makes the cross-module contract explicit and easier to test.

### Module Ownership

`models` owns the new `HarnessFunctionSchema.capture_evidence` field because `HarnessFunctionSchema` is the serializable cross-module action schema consumed by `agent`.

`core` owns the driver tool decorator flag and schema discovery flow because concrete driver methods and action-space schema generation live there.

`agent` owns the conversion from `schema.capture_evidence` to dynamic `EvidencePolicy` because dynamic evidence capture policy is agent-runtime behavior around SDK harness tool calls.

`cli`, `report`, `fsq`, and strict-core sequencing do not need behavior changes for this optimization.

## Error Handling And Edge Cases

`capture_evidence=False` is the default at every layer. Missing or false flags must produce the default empty `EvidencePolicy` used for read-only and assertion tools.

If `capture_evidence=True` and artifact capture fails, existing `StepRunner` behavior applies: the runner returns a failed `RunnerStepResult` with `failure_category="artifact_error"`, and `HarnessToolAdapter` surfaces that failure in the structured tool JSON.

Action-space discovery errors should remain startup configuration errors. Adding `capture_evidence` must not weaken the existing `_android_driver_tool(...)` validation against `ANDROID_ACTION_DEFINITIONS_BY_NAME`.

The new flag must not alter tool names, JSON parameter schemas, FSQ action provenance, or dynamic strict-case recording compatibility.

## Affected Specs Expected To Change

- `fsq_agent/models/SPEC.md`: document `HarnessFunctionSchema.capture_evidence` as a serializable action-schema flag and update the `HarnessFunctionSchema` public interface description.
- `fsq_agent/core/SPEC.md`: document `_android_driver_tool(..., capture_evidence=...)` / driver tool schema discovery as the source of reviewed dynamic evidence-capture intent for exposed driver tools.
- `fsq_agent/agent/SPEC.md`: replace the private UI-mutating action allowlist wording with schema-driven evidence policy from `HarnessFunctionSchema.capture_evidence`.

No root `SPEC.md`, `cli/SPEC.md`, `report/SPEC.md`, or `fsq/SPEC.md` changes are expected.

## Open Questions Resolved During Discussion

- The control point should be `_android_driver_tool(...)`, not a private adapter list.
- The parameter name should be `capture_evidence`.
- The flag should be an explicit `HarnessFunctionSchema.capture_evidence` field rather than hidden metadata.
- The optimization should not expand the dynamic tool surface; unexposed `performActions` remains unexposed in this change.
- `HarnessToolAdapter` remains responsible for translating the flag into the current standard dynamic before/after screenshot and UI-tree `EvidencePolicy`.

## Verification Expectations

Focused automated tests should cover:

- `_android_driver_tool(..., capture_evidence=True)` produces a `HarnessFunctionSchema` with `capture_evidence=True`.
- Existing decorated mutating tools such as `launch_app`, `tap_on`, `input_text`, `press_key`, and `swipe` expose `capture_evidence=True` through `action_space()`.
- Assertion and observation tools such as `assert_visible`, `assert_not_visible`, `assert_state`, and `ui_tree` expose `capture_evidence=False`.
- `HarnessToolAdapter` applies before/after/failure screenshot and UI-tree policy from `schema.capture_evidence=True`.
- `HarnessToolAdapter` keeps the default evidence policy for `schema.capture_evidence=False`.
- `_UI_MUTATING_ACTIONS` is no longer needed for dynamic evidence policy selection.
- Existing tool output fields used by reports and dynamic strict-case recording remain present.
- Existing strict runner and dynamic recording regression tests continue to pass.

Real-device acceptance should continue to use the dynamic Edge tap case from the 2026-06-17 design. A dynamic `tapOn` on the Edge overflow menu should still produce before and after screenshot and UI-tree artifacts under the dynamic run directory.

## Handoff

Next step: use `spec-driven` to update root/module `SPEC.md` files from this design before implementation.