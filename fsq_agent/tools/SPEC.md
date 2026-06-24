# Module: tools

## Purpose

Expose cross-platform local utility capabilities as SDK-neutral CommonTool capabilities declared through the shared `capabilities` decorator layer, provide the CommonTool executor binding used by `StepRunner`, and adapt registered CommonTool capabilities into OpenAI Agents SDK `FunctionTool` objects for the dynamic runtime. This module owns scoped file read/write, allowlisted runtime secret reads, bounded run-artifact search and slice reads, pure waits, CommonTool result normalization, CommonTool execution behavior, and safe CommonTool run-event metadata.

The tools module does not own platform actions, AI assertions, runtime progress events, local CLI execution, or shell execution. Platform actions and `assertWithAI` are harness capabilities exposed by `core` and adapted by `agent`; progress events are runtime-internal events emitted by `agent`; provider-backed AI evaluation is owned by `providers` and injected into platform harnesses by entry-layer code.

## Dependencies

- `models`: Uses `CapabilityDefinition`, `ReplayPolicy`, `CapabilityInvocation`, `CapabilityExecutionResult`, `CommonToolCall`, `CommonToolResult`, `ToolDefinition`, `ToolCall`, `ToolResult`, `RuntimeSecretSettings`, `LocalToolOutputSettings`, `RunEvent`, and `ToolExecutionError`.
- `capabilities`: Uses shared declaration decorators and discovery helpers for CommonTool capability metadata.

The tools module must not depend on `agent`, `providers`, `core`, `cli`, `config`, `knowledge`, `skills`, `report`, or any OpenAI Agents SDK type at import time. The Agents SDK adapter may import SDK classes lazily or accept SDK classes through dependency injection when building runtime tools.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `common_capability`: CommonTool-specific helper decorator from `capabilities` used by CommonTool implementations to declare canonical name, aliases, parameter model, step kind, replay policy, sensitivity, evidence policy, owner, and provenance metadata with `executor_kind="common"`.
- `capability`: Backward-compatible CommonTool decorator alias that resolves to the same shared declaration implementation as `common_capability`. It exists only for CommonTool author convenience and must not be a separate decorator implementation.
- `CommonToolProvider`: Protocol for a provider of SDK-neutral common capabilities. It exposes decorated `CapabilityDefinition` records and invokes one capability by canonical name with JSON-like arguments.
- `CommonToolRegistry`: Maintains the active decorated CommonTool capability set for the common executor binding and rejects duplicate canonical names. It is not the global capability registry.
- `CommonToolExecutor`: Routes `CommonToolCall` requests to registered decorated providers and returns normalized `CommonToolResult` values for `StepRunner` to wrap into runner results.
- `FileOps`: Performs scoped file reads and writes. Read roots include configured case, knowledge, and output directories; writes are restricted to the configured output root or current run output directory.
- `ToolArtifactStore`: Persists complete CommonTool outputs under the current run directory and provides bounded artifact search and slice reads.
- `DefaultCommonToolProvider`: Built-in provider for `read_file`, `write_file`, `get_runtime_secret`, `search_artifact`, `read_artifact_slice`, and `wait_ms`.
- `AgentsCommonToolAdapter`: Builds OpenAI Agents SDK `FunctionTool` objects from decorated CommonTool capability definitions while preserving SDK-neutral execution semantics and delegating execution through `StepRunner`.

The CommonTool names exposed in this SPEC cycle are:

| Tool name | Purpose |
|---|---|
| `read_file` | Read UTF-8 text from an allowed input/output path with bounded response size. |
| `write_file` | Write UTF-8 text below the configured output root or current run directory. |
| `get_runtime_secret` | Return an environment variable value only when its name is listed in `runtime_secrets.allowed_env_names`. |
| `search_artifact` | Search text artifacts below the current run directory and return bounded matches. |
| `read_artifact_slice` | Read a bounded byte or line slice from one current-run artifact path. |
| `wait_ms` | Sleep for an explicit duration without touching platform state. |

CommonTool replay metadata:

| Tool name | Recording behavior |
|---|---|
| `get_runtime_secret` | Declares `sensitivity=True` and `ReplayPolicy(kind="dependency", alias="runtimeSecret")`. The value is returned to the current model-facing tool result through `output.value`, but persisted events, previews, artifacts, reports, generated YAML, and recording manifests contain only safe dependency metadata. Dynamic run recording may bind later redacted harness arguments to `{runtimeSecret: NAME}` refs. |
| `wait_ms` | Declares `ReplayPolicy(kind="fsq_command", alias="waitMs")`. Dynamic run recording may convert successful normalized results into `waitMs` strict replay commands. |

`read_file`, `write_file`, `search_artifact`, and `read_artifact_slice` have no replay policy in this SPEC cycle and must not be converted into replay commands.

Removed from the public tools contract: `run_cli_tool`, SDK `ShellTool` construction/execution, public/common `submit_visual_assertion`, and public/common `publish_progress`.

## Internal Structure

- `__init__.py`: Public exports only.
- `_common.py`: CommonTool provider protocol, CommonTool registry, executor binding, built-in capability wiring, runtime-secret allowlist lookup, pure wait implementation, and use of shared `capabilities` decorators/discovery helpers for CommonTool metadata.
- `_agents_adapter.py`: OpenAI Agents SDK adapter that converts decorated CommonTool capability definitions into SDK `FunctionTool` objects and maps SDK calls into StepRunner-backed capability invocations.
- `_tool_artifacts.py`: Per-run CommonTool output artifact persistence plus bounded artifact search and slice helpers.
- `_file_ops.py`: Scoped file operations.
- `SPEC.md`: Module design.

## Python Architecture

- Architecture level: 2 Simple Package.
- Public API: CommonTool provider/executor interfaces, built-in CommonTool provider, scoped file/artifact/secret/wait utilities, CommonTool declaration helper/alias backed by `capabilities`, and SDK adapter exported from `__init__.py`.
- Internal modules: `_common.py`, `_agents_adapter.py`, `_tool_artifacts.py`, and `_file_ops.py` are private implementation modules.
- Domain boundaries: tool safety, scoped file access, secret allowlist checks, artifact bounds, and pure wait behavior live here. Global routing, evidence capture, replay decisions, and result/event normalization live in `core.StepRunner` using capability metadata.
- Boundary models: CommonTool invocation/result models and capability definitions come from `models`; runtime SDK objects remain adapter-local.
- Dependency direction: may import public symbols from `models` and `capabilities`; must not import `agent`, `providers`, `core`, `cli`, `config`, `knowledge`, `skills`, `report`, or SDK classes at import time.
- Rationale: the module owns focused utility behavior and metadata declaration without orchestration or persistence complexity requiring a higher level.

## Error Handling

During SDK-managed runs, recoverable CommonTool failures return model-visible structured error JSON so the agent can retry or report failure. Invalid configuration, duplicate tool names, invalid tool names, malformed arguments, path traversal, attempts to read or write outside allowed roots, secret allowlist violations, timeout exhaustion, artifact bounds violations, and malformed outputs raise or normalize to `ToolExecutionError` from `models` depending on whether the failure happens during construction or invocation.

Secret values must be redacted from `RunEvent` payloads, tool artifacts, historical model-facing outputs, final reports, recording manifests, generated YAML, and exception messages. The current model-facing `get_runtime_secret` tool result may include the actual value only in the standard `output.value` field. Secret diagnostics and replay metadata may include only the requested environment variable name, allowlist status, presence status, sensitivity markers, and replayability markers.

## Design Decisions

- CommonTool is SDK-neutral so the same capability core can be adapted to OpenAI Agents SDK now and another agent SDK later without rewriting file, artifact, wait, or secret safety policy.
- Shared capability declaration metadata is the source of truth for CommonTool schema, replay, sensitivity, and evidence behavior. The decorator and discovery implementation lives in `capabilities`; the adapter and recorder must not add replay or sensitivity behavior by checking names such as `get_runtime_secret` or `wait_ms`.
- The CommonTool core is intentionally small. Cross-platform tools are limited to file read/write, runtime secret lookup, artifact search/slice, and pure wait. More tools require a SPEC change.
- Local CLI and shell execution are removed from the first-cycle public tool surface. If command execution returns in the future, it must be redesigned as an explicitly scoped capability with its own SPEC update.
- `publish_progress` is not a CommonTool. Runtime progress is emitted directly by `agent` as `RunEvent` values so user-visible status does not consume a model tool call or become confused with external capabilities.
- `submit_visual_assertion` is not a CommonTool. Android `assertWithAI` is a platform assertion operation exposed by the active harness and evaluated through an injected provider-backed evaluator.
- CommonTool run events use capability metadata with `executor_kind="common"`, allowing reports and dynamic run recording to distinguish common local utilities from platform harness actions and runtime-internal records without hard-coded name sets.
- `get_runtime_secret` and `wait_ms` are the only CommonTools with replay metadata in this SPEC cycle. The adapter should emit enough structured, safe event payload metadata for the CLI recorder to reconstruct the requested secret name or wait duration without parsing redacted previews.
- SDK-managed CommonTools write complete raw results to per-run artifacts when CommonTool artifact output is enabled. Small and moderate current outputs may still return inline; oversized or historical outputs return artifact references, previews, and instructions to use `search_artifact` or `read_artifact_slice` only when more detail is needed.
- Artifact read tools only resolve paths inside the current run directory and enforce bounded search/slice results so artifact recovery cannot reintroduce unbounded context growth.
- `wait_ms` provides elapsed-time waits for FSQ pause semantics and page-load delays. It must be preferred over platform gestures when the intended action is waiting, because gestures can alter scroll position or UI state. Successful dynamic `wait_ms` calls may be recorded as strict `waitMs` replay commands.
- `get_runtime_secret` reads only environment variable names listed in `runtime_secrets.allowed_env_names`. It is intended for setup flows such as account sign-in where credentials must stay out of FSQ YAML and source code. Successful dynamic calls may be recorded only as runtime-secret name dependencies, never as secret values.
- File operation tools treat `cases.dir` and configured knowledge directories as read-only inputs and write generated files only under managed output directories.
- Platform action execution remains outside the tools module. The active harness exposes platform action schemas, and the `agent` module adapts those schemas to SDK `FunctionTool` objects.
