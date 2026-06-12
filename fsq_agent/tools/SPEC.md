# Module: tools

## Purpose

Expose cross-platform local utility capabilities through an SDK-neutral CommonTool interface, then adapt those capabilities into OpenAI Agents SDK `FunctionTool` objects for the dynamic runtime. This module owns scoped file read/write, allowlisted runtime secret reads, bounded run-artifact search and slice reads, pure waits, CommonTool result normalization, and CommonTool run-event metadata.

The tools module does not own platform actions, AI assertions, runtime progress events, local CLI execution, or shell execution. Platform actions and `assertWithAI` are harness capabilities exposed by `core` and adapted by `agent`; progress events are runtime-internal events emitted by `agent`; provider-backed AI evaluation is owned by `providers` and injected into platform harnesses by entry-layer code.

## Dependencies

- `models`: Uses `CommonToolDefinition`, `CommonToolCall`, `CommonToolResult`, `ToolDefinition`, `ToolCall`, `ToolResult`, `RuntimeSecretSettings`, `LocalToolOutputSettings`, `RunEvent`, and `ToolExecutionError`.

The tools module must not depend on `agent`, `providers`, `core`, `cli`, `config`, `knowledge`, `skills`, `report`, or any OpenAI Agents SDK type at import time. The Agents SDK adapter may import SDK classes lazily or accept SDK classes through dependency injection when building runtime tools.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `CommonToolProvider`: Protocol for a provider of SDK-neutral common capabilities. It exposes serializable capability definitions and invokes one capability by name with JSON-like arguments.
- `CommonToolRegistry`: Maintains the active CommonTool capability set and rejects duplicate tool names.
- `CommonToolExecutor`: Routes `CommonToolCall` requests to registered providers and returns normalized `CommonToolResult` values.
- `FileOps`: Performs scoped file reads and writes. Read roots include configured case, knowledge, and output directories; writes are restricted to the configured output root or current run output directory.
- `ToolArtifactStore`: Persists complete CommonTool outputs under the current run directory and provides bounded artifact search and slice reads.
- `DefaultCommonToolProvider`: Built-in provider for `read_file`, `write_file`, `get_runtime_secret`, `search_artifact`, `read_artifact_slice`, and `wait_ms`.
- `AgentsCommonToolAdapter`: Builds OpenAI Agents SDK `FunctionTool` objects from the active `CommonToolRegistry` while preserving SDK-neutral execution semantics.

The CommonTool names exposed in this SPEC cycle are:

| Tool name | Purpose |
|---|---|
| `read_file` | Read UTF-8 text from an allowed input/output path with bounded response size. |
| `write_file` | Write UTF-8 text below the configured output root or current run directory. |
| `get_runtime_secret` | Return an environment variable value only when its name is listed in `runtime_secrets.allowed_env_names`. |
| `search_artifact` | Search text artifacts below the current run directory and return bounded matches. |
| `read_artifact_slice` | Read a bounded byte or line slice from one current-run artifact path. |
| `wait_ms` | Sleep for an explicit duration without touching platform state. |

Removed from the public tools contract: `run_cli_tool`, SDK `ShellTool` construction/execution, public/common `submit_visual_assertion`, and public/common `publish_progress`.

## Internal Structure

- `__init__.py`: Public exports only.
- `_common.py`: `CommonToolProvider` protocol, registry, executor, and built-in capability wiring.
- `_agents_adapter.py`: OpenAI Agents SDK adapter that converts CommonTool definitions into SDK `FunctionTool` objects and maps SDK calls back to `CommonToolExecutor`.
- `_tool_artifacts.py`: Per-run CommonTool output artifact persistence plus bounded artifact search and slice helpers.
- `_file_ops.py`: Scoped file operations.
- `_secrets.py`: Runtime secret allowlist lookup and redaction helpers.
- `_wait.py`: Pure wait helper.
- `_compat.py`: Temporary compatibility shims only when needed during migration; compatibility symbols must not be part of the target public interface.
- `SPEC.md`: Module design.

## Error Handling

During SDK-managed runs, recoverable CommonTool failures return model-visible structured error JSON so the agent can retry or report failure. Invalid configuration, duplicate tool names, invalid tool names, malformed arguments, path traversal, attempts to read or write outside allowed roots, secret allowlist violations, timeout exhaustion, artifact bounds violations, and malformed outputs raise or normalize to `ToolExecutionError` from `models` depending on whether the failure happens during construction or invocation.

Secret values must be redacted from `RunEvent` payloads, tool artifacts, model-facing previews, final reports, and exception messages. Secret diagnostics may include only the requested environment variable name, allowlist status, and presence status.

## Design Decisions

- CommonTool is SDK-neutral so the same capability core can be adapted to OpenAI Agents SDK now and another agent SDK later without rewriting file, artifact, wait, or secret safety policy.
- The CommonTool core is intentionally small. Cross-platform tools are limited to file read/write, runtime secret lookup, artifact search/slice, and pure wait. More tools require a SPEC change.
- Local CLI and shell execution are removed from the first-cycle public tool surface. If command execution returns in the future, it must be redesigned as an explicitly scoped capability with its own SPEC update.
- `publish_progress` is not a CommonTool. Runtime progress is emitted directly by `agent` as `RunEvent` values so user-visible status does not consume a model tool call or become confused with external capabilities.
- `submit_visual_assertion` is not a CommonTool. Android `assertWithAI` is a platform assertion operation exposed by the active harness and evaluated through an injected provider-backed evaluator.
- CommonTool run events use tool origin `common`, allowing reports to distinguish common local utilities from platform harness actions and runtime-internal records.
- SDK-managed CommonTools write complete raw results to per-run artifacts when CommonTool artifact output is enabled. Small and moderate current outputs may still return inline; oversized or historical outputs return artifact references, previews, and instructions to use `search_artifact` or `read_artifact_slice` only when more detail is needed.
- Artifact read tools only resolve paths inside the current run directory and enforce bounded search/slice results so artifact recovery cannot reintroduce unbounded context growth.
- `wait_ms` provides elapsed-time waits for FSQ pause semantics and page-load delays. It must be preferred over platform gestures when the intended action is waiting, because gestures can alter scroll position or UI state.
- `get_runtime_secret` reads only environment variable names listed in `runtime_secrets.allowed_env_names`. It is intended for setup flows such as account sign-in where credentials must stay out of FSQ YAML and source code.
- File operation tools treat `cases.dir` and configured knowledge directories as read-only inputs and write generated files only under managed output directories.
- Platform action execution remains outside the tools module. The active harness exposes platform action schemas, and the `agent` module adapts those schemas to SDK `FunctionTool` objects.
