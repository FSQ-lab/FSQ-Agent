# Harness Function Schema Execution Design

Date: 2026-06-11

## Goal

Retire MCP from the execution capability path and make the harness layer the single source of platform action function-call schemas.

OpenAI Agents SDK should continue to own the overall model turn and function-call loop, but the SDK must receive platform action tools generated from `HarnessInterface.action_space()` rather than MCP `list_tools()` output. The model should see harness/driver action names such as `tap_on`, `input_text`, and `assert_visible`, and each call should execute through the FSQ-owned harness contract.

## Scope

This design covers the goal-driven OpenAI agent execution path and its connection to the existing harness contracts. It also identifies the specification updates needed to remove MCP from current public behavior.

In scope:

- Generate SDK `FunctionTool` objects for platform actions from `HarnessFunctionSchema` records returned by `HarnessInterface.action_space()`.
- Route each harness function call through `HarnessInterface.get_context()` and `HarnessInterface.invoke_action()`.
- Keep OpenAI Agents SDK as the runtime that owns model turns, tool-call continuation, streaming events, and structured final output.
- Remove MCP as a model-visible tool source, schema source, lifecycle path, validation path, and backend abstraction.
- Preserve local non-platform utility tools where they remain useful, such as progress publishing, artifact search/slice, waits, runtime secrets, and file or CLI tools controlled by configuration.
- Use Android as the first concrete platform path because `AndroidHarness.action_space()` already produces driver-backed `HarnessFunctionSchema` records.

## Non-Goals

- Do not replace OpenAI Agents SDK as the overall agent loop runtime.
- Do not introduce a versioned compatibility switch, migration mode, or alternate runtime selector.
- Do not keep MCP as a temporary backend for platform execution or lifecycle setup.
- Do not update root or module `SPEC.md` files in this design step.
- Do not implement code from this design document before the relevant `SPEC.md` files are updated and confirmed.
- Do not define every future platform driver. Android is the first concrete target; other platforms should follow the same harness contract later.

## Proposed Design

### Architecture

The runtime should construct platform action tools from the harness instead of MCP servers.

```text
Task + knowledge + skills
        |
        v
OpenAIAgentsRuntime
        |
        +--> construct or receive configured harness
        +--> read harness.action_space()
        +--> convert HarnessFunctionSchema records to SDK FunctionTool objects
        +--> create Agent(tools=[local tools + harness tools], mcp_servers=[])
        |
        v
OpenAI Agents SDK function-call loop
        |
        +--> model calls harness function tool
        +--> adapter builds ExecutableStep
        +--> adapter calls HarnessInterface.invoke_action()
        +--> harness calls concrete driver
        +--> adapter returns compact action result JSON
        |
        v
Structured final output + verification + reports
```

MCP is not a backend abstraction in the new design. Backend selection is represented by harness and driver classes, such as `AndroidHarness` plus a concrete Android driver.

### Module Ownership

`models` owns serializable contracts only:

- `HarnessFunctionSchema`
- `ExecutableStep`
- `HarnessActionResult`
- `HarnessArtifactRef`
- shared failure categories
- Android parameter models and Android action registry

`models` must not store OpenAI Agents SDK runtime objects.

`core` owns harness execution semantics:

- `HarnessInterface.action_space()` remains the platform action schema source.
- `HarnessInterface.invoke_action()` remains the platform action execution entry.
- `AndroidHarness` continues to validate action parameters, dispatch to the driver, classify failures, and return `HarnessActionResult`.
- `core` must not import OpenAI Agents SDK and must not know whether a call came from an agent, CLI, or strict core runner.

`agent` owns the SDK-facing harness bridge:

- Convert each `HarnessFunctionSchema` into one SDK `FunctionTool`.
- Adapt SDK tool JSON arguments into `ExecutableStep` records.
- Call the supplied harness and serialize harness results back to model-visible JSON.
- Emit normal run events with `tool_origin="harness"` for platform action calls.
- Create SDK `Agent` instances with no MCP servers.

`tools` owns local utility tools only:

- Keep local tools that are not platform execution backends.
- Remove MCP factory, MCP validation, MCP caller, and MCP lifecycle responsibilities from the current runtime contract.

`config` owns runtime construction settings:

- Remove MCP server and MCP validation settings from active configuration.
- Define or confirm explicit harness and driver settings for platform, Android backend, app id, serial or device options, artifact store wiring, and AI assertion evaluator enablement.

`cli` owns entry construction:

- Build the configured harness and driver.
- Pass the harness into `FsqAgent` or `OpenAIAgentsRuntime`.
- Keep strict-core commands on the existing direct `StepRunner` plus `AndroidHarness` path.

### Harness Tool Adapter Behavior

The harness tool adapter should be the only SDK-facing bridge for platform action tools.

For each `HarnessFunctionSchema`:

- Use `name` as the SDK function tool name.
- Use `description` as the SDK function tool description.
- Use `params_json_schema` as the SDK function parameter schema.
- Preserve `strict`, `platform`, `driver_method`, `fsq_action_name`, and `metadata` in adapter-side provenance and event payloads.

When the SDK invokes a harness tool:

1. Parse the JSON argument string into a dictionary.
2. Build an `ExecutableStep` with a generated runtime step id.
3. Set `ExecutableStep.action_name` to `fsq_action_name` when present; otherwise use the harness schema name.
4. Store model-facing tool name, platform, driver method, and schema metadata in `ExecutableStep.metadata`.
5. Call `harness.get_context()`.
6. Call `harness.invoke_action(step, context)`.
7. Serialize the `HarnessActionResult` into compact JSON for the model.

The adapter should not call driver methods directly. Parameter validation and side-effect control stay in the harness.

### Public Behavior

Configured MCP servers should no longer appear in runtime startup, capability listing, validation diagnostics, event logs, or reports.

Agent-visible platform tools should appear as harness tools. Reports should reconstruct real platform action calls from run events with:

- tool name
- origin `harness`
- arguments
- status
- failure category
- output preview
- artifact references
- platform and driver metadata when available

Android execution should use harness and driver configuration rather than Appium MCP server configuration. The first concrete path should use the existing Android harness action-space contract and the configured Android driver.

Strict-core FSQ execution remains direct through `StepRunner`, `StepSequenceRunner`, and `AndroidHarness`. This design connects the goal-driven OpenAI agent loop to the same harness layer; it does not replace strict-core execution.

## Error Handling

- If harness construction fails, runtime startup fails before external actions begin and returns a failed `StepResult`.
- If `harness.action_space()` fails, runtime startup fails before external actions begin and returns a failed `StepResult` with a harness action-space diagnostic.
- If a `HarnessFunctionSchema` cannot be converted into an SDK `FunctionTool`, runtime startup fails with a configuration error. The runtime must not silently expose a partial platform action list.
- If the model calls a harness tool with invalid JSON arguments, the adapter returns a failed tool result JSON with `status="failed"` and `failure_category="configuration_error"`.
- If `harness.get_context()` fails, the adapter returns `failure_category="context_error"` and records a harness tool failure event.
- If `harness.invoke_action()` returns a failed `HarnessActionResult`, the SDK tool call itself should complete at transport level and return JSON describing the action failure. This lets the model decide whether to report failure, gather more evidence, or continue within the task policy.
- If `harness.invoke_action()` raises unexpectedly, the adapter should classify the error through `harness.classify_error()` when possible and return failed JSON with failure category and message.
- Artifact references from `HarnessActionResult.artifact_refs` should be included in tool output JSON and persisted in reports. Binary artifact content must not be embedded in model-visible output.
- There is no MCP schema validation fallback. Harness schemas are the only platform action parameter schema source.

## Affected Specs Expected To Change

The next spec-driven step should update these files:

- `SPEC.md`: Update project module descriptions and architecture language so the project no longer advertises MCP execution.
- `fsq_agent/models/SPEC.md`: Remove MCP config and validation models from the current public contract. Clarify that `HarnessFunctionSchema` is the single platform action function-call schema source.
- `fsq_agent/core/SPEC.md`: Confirm `HarnessInterface.action_space()` feeds both strict-core execution metadata and agent-loop platform action tools.
- `fsq_agent/agent/SPEC.md`: Replace MCP server/tool loop wording with harness tool adapter behavior while keeping OpenAI Agents SDK as the function-call loop runtime.
- `fsq_agent/tools/SPEC.md`: Remove MCP factory, MCP validator, MCP caller, and lifecycle responsibilities. Keep local utility tool responsibilities only.
- `fsq_agent/config/SPEC.md`: Remove MCP runtime settings and define harness/driver construction settings.
- `fsq_agent/cli/SPEC.md`: Describe CLI/runtime harness construction and passing the harness into agent execution.
- `docs/openai-agent-loop.md`: Update explanatory flow so the SDK calls local and harness tools, not MCP tools.

## Open Questions Resolved During Discussion

- Replacement scope: MCP should be removed from the future execution path, not merely hidden from the model for one platform.
- Migration strategy: hard cut removal. No compatibility switch or versioned runtime mode should be introduced because the project has not been externally released.
- SDK role: OpenAI Agents SDK remains responsible for the overall agent loop and function-call continuation.
- Chosen approach: use a harness `FunctionTool` adapter. Do not move the whole execution loop into core runner for this change.

## Verification Expectations

Implementation should be verified at three levels.

Unit tests for the harness tool adapter should prove that it:

- Converts each `HarnessFunctionSchema` into one SDK `FunctionTool`.
- Preserves tool name, description, strict parameter JSON schema, platform, driver method, and `fsq_action_name`.
- Converts SDK tool JSON arguments into an `ExecutableStep`.
- Calls `harness.get_context()` before `harness.invoke_action()`.
- Serializes `HarnessActionResult` into bounded model-visible JSON.
- Handles invalid JSON, context errors, failed harness results, and unexpected exceptions without calling MCP.

Runtime tests for the OpenAI agent loop should prove that:

- `OpenAIAgentsRuntime` creates SDK agents with no MCP servers.
- Runtime tools include local utilities plus harness-generated platform tools.
- MCP validation diagnostic steps are absent.
- Platform action events use `tool_origin="harness"`.
- A failed harness action is returned as structured tool result JSON rather than hidden as an SDK transport failure.

Removal tests should prove that:

- MCP config and validation settings are no longer active runtime configuration.
- MCP factory, validator, caller, and lifecycle behavior are removed from public exports and specs.
- Docs and README no longer describe MCP as an execution path.
- Reports reconstruct harness tool calls correctly.

## Audit Expectations

Before completion is claimed, the independent diff-based SPEC implementation audit should check that:

- No agent runtime path passes MCP servers into OpenAI Agents SDK.
- No model-visible platform action schema is sourced from MCP `list_tools()`.
- `HarnessFunctionSchema` remains serializable and model-owned.
- `core` still does not import OpenAI Agents SDK.
- `agent` owns only the SDK bridge, not platform-specific driver behavior.
- No compatibility switch or migration mode was introduced.
- Strict-core execution remains direct through `StepRunner` and `AndroidHarness`.

## Self-Review Notes

- The design has one cohesive scope: remove MCP from execution and expose harness function schemas to the SDK agent loop.
- The design does not contain placeholder requirements.
- The design does not require implementation before `SPEC.md` updates.
- The design keeps OpenAI Agents SDK in the loop, matching the confirmed approach.
- The design avoids a compatibility branch and assumes the project can hard cut the current runtime contract.