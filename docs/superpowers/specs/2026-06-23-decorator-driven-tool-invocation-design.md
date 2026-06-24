# Decorator-Driven Tool Invocation Design

Date: 2026-06-23
Status: Ready for user review

## Goal

Unify all executable FSQ-Agent capabilities behind one decorator-driven invocation system so future iteration starts from a clean execution architecture instead of preserving today's split internal paths.

The unified system covers CommonTool capabilities such as `wait_ms` and `get_runtime_secret`, harness-owned capabilities such as explicit platform AI assertions, and driver/platform capabilities such as Android `tap_on`, `input_text`, `press_key`, and `swipe`.

Every executable capability should declare schema, executor routing, recording, sensitivity, replay, evidence, ownership, and provenance through decorator metadata. Dynamic LLM execution and strict replay execution should both pass through `StepRunner`, and `StepRunner` should use the decorated registry to decide which backend to invoke, whether to capture evidence, how to redact sensitive values, and how to emit structured events and results.

`wait_ms` and `get_runtime_secret` must not be special branches. They are ordinary decorated CommonTool capabilities. Strict `waitMs` replay syntax resolves through the same registry to the decorated `wait_ms` implementation.

## Scope

This design covers executable capability declaration, registry bootstrap, FSQ YAML parsing, dynamic SDK tool exposure, strict replay execution, dynamic recording, sensitivity handling, and event/result provenance.

Affected modules:

- `models`: shared capability metadata, invocation, result, replay, and registry snapshot contracts.
- `tools`: decorated CommonTool declarations and CommonTool execution binding.
- `core`: unified `StepRunner` execution, harness/driver routing, and evidence/event normalization.
- `fsq`: registry-driven YAML action and replay alias parsing.
- `agent`: registry-driven OpenAI Agents SDK tool exposure and dynamic execution through `StepRunner`.
- `cli`: registry bootstrap before strict YAML parsing, dynamic recording from structured capability event payloads, and strict replay secret resolution.
- `report`: tool origin and tool-call reconstruction from structured event metadata rather than hard-coded tool-name sets.

## Non-Goals

This design does not implement code and does not update `SPEC.md` files. The next SDD step is to translate this confirmed design into root and module SPEC changes.

This design does not preserve old internal Python APIs as public compatibility surfaces. The repository is still in development and has not shipped this internal architecture, so implementation should prefer clean target structure over compatibility shims.

This design does not add locator fallback, AI repair, testcase mutation, recovery mode, or new platform semantics. Strict replay remains deterministic. Dynamic execution may adapt through model planning, but each concrete capability invocation still follows the same registry and `StepRunner` path.

This design does not require real Android device or backend connection during registry bootstrap or YAML parsing. Backend connection is delayed until execution of a backend capability that actually needs it.

## Selected Approach

Use decorator metadata as the single source of truth for executable capabilities.

Startup builds a lightweight `CapabilityRegistry` from decorated CommonTool, harness, and driver/platform capability hosts. The registry is validated before YAML parsing or SDK tool exposure. It is the authoritative source for capability names, aliases, schemas, executor routing, replay behavior, sensitivity, evidence capture, step kind, platform ownership, and provenance.

`StepRunner` becomes the top-level execution manager for both dynamic and strict paths. Adapters and parsers create canonical invocation records; they do not decide backend routing, recordability, sensitivity, evidence, or replay behavior themselves.

## Target Capability Model

A single target capability definition replaces today's split authority across CommonTool definitions, harness function schemas, and Android action definitions.

```python
class CapabilityDefinition:
    name: str
    aliases: list[str]
    executor_kind: Literal["common", "harness", "driver"]
    params_model: type[BaseModel]
    step_kind: Literal["action", "assertion", "observation", "setup", "teardown", "diagnostic"]
    description: str
    platform: str | None
    backend: str | None
    owner: str | None
    capture_evidence: bool
    sensitivity: bool
    replay: ReplayPolicy | None

class ReplayPolicy:
    kind: Literal["fsq_command", "dependency"]
    alias: str
```

`name` is the canonical runtime name used by `ExecutableStep.action_name`, SDK tool names, and `StepRunner` lookup. Examples include `wait_ms`, `get_runtime_secret`, `tap_on`, and `input_text`.

`aliases` contains authored or external names accepted by parser/tool layers. Examples include `waitMs`, `tapOn`, and `inputText`.

`executor_kind` describes runtime dispatch only: `common` routes to the CommonTool executor binding, `harness` routes to a harness-owned handler, and `driver` routes through the active harness to the platform driver/backend.

`replay` describes recording/replay encoding, not execution routing. `ReplayPolicy(kind="fsq_command", alias="waitMs")` records a command; `ReplayPolicy(kind="dependency", alias="runtimeSecret")` records a dependency.

Examples:

| Capability | Executor | Replay |
|---|---|---|
| `wait_ms` | `common` | `ReplayPolicy(kind="fsq_command", alias="waitMs")` |
| `get_runtime_secret` | `common` | `ReplayPolicy(kind="dependency", alias="runtimeSecret")` |
| `tap_on` | `driver` | `ReplayPolicy(kind="fsq_command", alias="tapOn")` |
| `read_file` | `common` | `None` |

## Decorator Examples

```python
@capability(
    name="wait_ms",
    aliases=["waitMs"],
    executor_kind="common",
    params_model=WaitMsParams,
    step_kind="action",
    description="Wait without touching or changing platform state.",
    replay=ReplayPolicy(kind="fsq_command", alias="waitMs"),
)
async def wait_ms(...):
    ...
```

```python
@capability(
    name="get_runtime_secret",
    aliases=["runtimeSecret"],
    executor_kind="common",
    params_model=RuntimeSecretParams,
    step_kind="diagnostic",
    description="Read one allowlisted runtime secret for the current run.",
    sensitivity=True,
    replay=ReplayPolicy(kind="dependency", alias="runtimeSecret"),
)
async def get_runtime_secret(...):
    ...
```

```python
@capability(
    name="tap_on",
    aliases=["tapOn"],
    executor_kind="driver",
    params_model=AndroidTapOnParams,
    step_kind="action",
    platform="android",
    backend="uiautomator2",
    capture_evidence=True,
    replay=ReplayPolicy(kind="fsq_command", alias="tapOn"),
)
def tap_on(...):
    ...
```

```python
@capability(
    name="assert_with_ai",
    aliases=["assertWithAI"],
    executor_kind="harness",
    params_model=AndroidAssertWithAIParams,
    step_kind="assertion",
    platform="android",
    replay=ReplayPolicy(kind="fsq_command", alias="assertWithAI"),
)
def assert_with_ai(...):
    ...
```

## Initialization Order

Every execution entry point uses the same bootstrap sequence:

1. Load settings.
2. Construct lightweight capability hosts for CommonTools, harnesses, and driver/platform backends.
3. Import and register decorated capabilities.
4. Build and validate `CapabilityRegistry`.
5. Parse FSQ YAML using the registry when strict replay is requested.
6. Create `StepRunner` with the registry and executor bindings.
7. Execute dynamic or strict invocations through `StepRunner`.

The lightweight Android driver/harness created during bootstrap must not connect to a real device. Real backend connection is lazy and happens only when a driver/platform capability is executed.

## Registry Validation

Registry bootstrap fails fast before YAML parsing or SDK tool exposure when the capability graph is inconsistent.

Validation rules:

- Canonical capability names are unique.
- Aliases are deterministic. A YAML action or SDK-facing alias resolves to exactly one capability.
- `replay.alias` values do not create ambiguous strict replay parsing.
- Every capability has a resolvable parameter model and JSON schema.
- Every `executor_kind` has an executor binding available for the entry mode.
- `sensitivity=True` capabilities use the standard sensitive result shape.
- Capability hosts are lightweight at bootstrap. Real backend connection during registry build is a lifecycle bug.

## StepRunner Execution

`StepRunner` owns execution routing and event/result normalization.

It receives or holds `CapabilityRegistry`, a CommonTool executor binding, the active harness binding, driver/harness binding resolution, and evidence/event dependencies.

For each invocation, `StepRunner` should:

1. Look up the canonical capability by `ExecutableStep.action_name`.
2. Validate params with `capability.params_model`.
3. Build an invocation context containing run id, step id, source ref, authored action metadata, and capability metadata.
4. Apply evidence policy from capability metadata.
5. Route by `executor_kind`.
6. Normalize backend output into one result contract.
7. Apply sensitivity rules.
8. Emit structured events containing safe capability metadata and replay payload fields.
9. Return a `RunnerStepResult`.

`StepRunner` does not contain action-name branches for `waitMs`, `wait_ms`, `get_runtime_secret`, or Android actions. A pure wait is a `common` capability with no harness context requirement. Runtime secret lookup is a sensitive `common` capability.

## Dynamic Execution Flow

Dynamic execution exposes SDK tools from the registry through a thin adapter:

1. Convert each dynamic capability into an SDK `FunctionTool`.
2. Use `capability.name` as the SDK tool name.
3. Use capability schema and description from the registry.
4. Parse SDK JSON arguments into an invocation.
5. Call `StepRunner`.
6. Serialize the normalized result for the model.

The adapter must not decide recordability, replay behavior, sensitivity, tool origin, or evidence policy by checking tool names. SDK streamed `tool_called` events may still provide started events, but completed/failed event payloads used by recording and reports should come from the normalized capability result produced by `StepRunner`.

## Strict Replay Flow

Strict CLI execution must bootstrap the registry before parsing YAML.

Flow:

1. Load settings.
2. Build lightweight capability registry.
3. Load FSQ case YAML.
4. Parse commands with `FsqExecutableStepAdapter(registry_snapshot)`.
5. Resolve `{runtimeSecret: NAME}` references in memory.
6. Run steps through `StepSequenceRunner` and `StepRunner`.
7. Write strict evidence and reports.

`FsqExecutableStepAdapter` no longer imports or depends on an Android static action table. It resolves YAML command names through the registry: `tapOn -> tap_on`, `inputText -> input_text`, `waitMs -> wait_ms`, and `assertWithAI -> assert_with_ai`.

Generated `ExecutableStep.action_name` stores the canonical capability name. The authored YAML command name is preserved in metadata:

```python
metadata={
    "authored_action_name": "waitMs",
    "capability_name": "wait_ms",
}
```

Strict `waitMs` reaches the same decorated `wait_ms` CommonTool implementation used by dynamic `wait_ms`.

## Recording And Replay

Dynamic recording remains a CLI-owned post-run transformation, but it consumes structured capability metadata emitted by `StepRunner` instead of hard-coded tool names or output previews.

Completed event payloads should include safe fields such as `capability_name`, `aliases`, `executor_kind`, `step_kind`, `platform`, `backend`, `owner`, `replay`, `sensitivity`, `safe_replay_params`, and dependency metadata when applicable.

Recorder rules:

- `capability.replay is None`: skip; capability is diagnostic-only for recording.
- `capability.replay.kind == "fsq_command"`: append `{capability.replay.alias: safe_replay_params}` to generated strict YAML.
- `capability.replay.kind == "dependency"`: record dependency metadata without adding a strict step.

This records `wait_ms` as `waitMs`, `tap_on` as `tapOn`, and `get_runtime_secret` only as a runtime secret dependency. `read_file`, `write_file`, artifact search, and artifact slice reads are not replayed unless they declare a replay policy in a future SPEC update.

Recorder must not parse truncated model previews. It should trust only structured event payload produced from capability metadata and normalized results.

## Sensitivity

Sensitivity is intentionally simple:

```python
sensitivity=True
```

This means the capability result is sensitive and the sensitive actual value is read from the standard normalized result field `output.value`.

Rules:

- Current model-facing tool output may include the real value only for the immediate tool result that requested it.
- Persisted events, event previews, reports, recording manifests, generated YAML, artifact previews, and historical tool-output trimming must replace the sensitive value with `"***"` or omit the sensitive output entirely.
- Historical sensitive tool outputs should be replaced with a message such as `[Sensitive historical get_runtime_secret output omitted.]`.
- A `sensitivity=True` capability that does not return the standard `output.value` shape fails as a capability implementation/configuration error, and raw output must not be persisted.

General key-name redaction may remain as defense in depth, but field lists such as `redact_fields=["value"]` are not part of the capability contract.

## Target Deletions

The target implementation should delete split authority and normal-path name branching rather than preserving it.

Remove these as authoritative structures:

- `ANDROID_ACTION_DEFINITIONS_BY_NAME` as the Android action source of truth.
- `AndroidActionDefinition` as the Android action contract.
- `HarnessFunctionSchema` as a separate platform schema contract.
- `CommonToolDefinition` as a separate CommonTool schema contract.

Remove these normal-path branches:

- `StepRunner` special handling for `action_name == "waitMs"`.
- CommonTool adapter branches that add replay/sensitivity metadata by checking `tool_name == "get_runtime_secret"` or `tool_name == "wait_ms"`.
- Runtime/report/verifier hard-coded common tool name sets used to infer `tool_origin`.
- Recorder branches that decide replay behavior from tool names.

Temporary development-only helpers are acceptable while landing the change, but the target SPEC should describe the unified capability system as the desired architecture, not compatibility wrappers around the old one.

## Error Handling And Edge Cases

Registry bootstrap failures are configuration errors and must happen before external UI actions.

YAML parsing failures are configuration errors when an authored action or replay alias cannot be resolved through the registry or when params do not validate against the capability parameter model.

Runtime secret replay references remain entry-layer responsibilities. Strict replay resolves `{runtimeSecret: NAME}` only in memory, validates allowlist membership and environment presence, then validates the resolved payload against the target capability params model before execution.

Driver target misses, assertion failures, action errors, artifact errors, and backend exceptions still become structured runner results. `StepRunner` owns consistent phase/result conversion across CommonTool, harness-owned, and driver-owned capabilities.

Strict mode continues to reject silent recovery. A strict miss remains a failed strict result unless a future recovery mode explicitly runs separately with its own evidence.

## Affected Specs Expected To Change

- `SPEC.md`: update project-level descriptions of `tools`, `core`, `fsq`, `agent`, `cli`, dynamic recording, strict replay, and module architecture so decorated capabilities and `StepRunner` are the common execution path.
- `fsq_agent/models/SPEC.md`: add unified capability metadata, replay policy, invocation/result, registry snapshot, and simplified sensitivity contracts; remove static Android action registry as source of truth.
- `fsq_agent/tools/SPEC.md`: describe decorated CommonTool declarations and CommonTool executor binding under the unified capability system.
- `fsq_agent/core/SPEC.md`: describe `StepRunner` as the single execution manager for common, harness, and driver capabilities; remove core-owned `waitMs` special behavior.
- `fsq_agent/fsq/SPEC.md`: describe registry-driven YAML parsing and alias resolution for strict replay.
- `fsq_agent/agent/SPEC.md`: describe registry-driven SDK tool exposure and dynamic invocation through `StepRunner`.
- `fsq_agent/cli/SPEC.md`: describe registry bootstrap before strict parsing and recording from structured capability replay metadata.
- `fsq_agent/report/SPEC.md`: describe tool-call reconstruction from structured event metadata instead of hard-coded tool name sets.

## Open Questions Resolved During Discussion

- Decorator metadata, not a static Android action table, is the target source of truth.
- Registry bootstrap occurs before YAML parsing.
- Registry bootstrap may initialize lightweight capability hosts, but real device/backend connection is delayed until execution.
- Internal compatibility with the current unpublished Python structure is not a design goal.
- `sensitivity=True` is sufficient; sensitive values are read from the standard `output.value` shape.
- `executor_kind` remains execution routing metadata.
- Replay behavior is expressed as an optional nested `ReplayPolicy`, not by parallel top-level `replay_kind` and `replay_alias` fields.
- `wait_ms` and `get_runtime_secret` are ordinary CommonTool capabilities, not special branches.
- Strict `waitMs` resolves to the same decorated `wait_ms` implementation used by dynamic execution.

## Verification Expectations

Automated verification should prove the new structure, not merely preserve old tests.

Required checks:

- Registry bootstrap works without connecting a real Android device.
- Duplicate capability names and ambiguous aliases fail fast.
- Strict YAML `waitMs` parses to canonical `wait_ms`.
- Strict YAML Android actions parse to canonical decorated capability names such as `tap_on` and `input_text`.
- Dynamic `wait_ms` and strict `waitMs` execute through the same decorated implementation.
- `StepRunner` has no `waitMs` action-name special branch.
- CommonTool SDK adapter has no `get_runtime_secret` or `wait_ms` name-based replay/sensitivity branches.
- FSQ parser does not import or consult a static Android action registry.
- Recorder decides replay from structured `ReplayPolicy` metadata, not tool names.
- Report and verifier tool-origin reconstruction use structured event metadata, not hard-coded common tool name sets.
- `get_runtime_secret` returns the current model-facing value through `output.value` but persists only redacted data.
- `read_file` is `executor_kind="common"` but is not recorded when it has no replay policy.
- Dynamic mutating Android actions receive evidence policy from capability metadata.
- Strict runtime secret references are resolved in memory and never written to generated YAML, events, manifests, reports, or artifact previews.

## Handoff

Next step: use `spec-driven` to update root/module `SPEC.md` files from this design before implementation.