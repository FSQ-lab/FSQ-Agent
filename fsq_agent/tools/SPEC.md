# Module: tools

## Purpose

Expose configured local utility capabilities as OpenAI Agents SDK tools. The OpenAI Agents SDK runner owns the model tool loop; this module owns local command/file safety, runtime secret access controls, local SDK tool construction, artifact search/slice utilities, pure waits, visual assertion submission, and optional shell command execution. Platform action tools are generated from harness schemas by the `agent` module, not by `tools`.

## Dependencies

- `models`: Uses `ToolDefinition`, `ToolCall`, `ToolResult`, `CLIToolConfig`, `ShellSettings`, `RuntimeSecretSettings`, `SkillBundle`, `Task`, `RunEvent`, and `ToolExecutionError`.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `CapabilityRegistry`: Maintains discovered local CLI and file operation capabilities for diagnostics and CLI display.
- `CLIRunner`: Executes configured CLI commands asynchronously with timeout, output capture, and a configured workspace current working directory.
- `FileOps`: Performs scoped file reads and writes. Read roots include configured case, knowledge, and output directories; writes are restricted to the configured output root.
- `AgentsToolFactory`: Builds OpenAI Agents SDK `FunctionTool` objects for CLI and file operations, artifact search/slice operations, a progress publication tool for user-visible planning updates, a pure wait tool, an explicit visual assertion submission tool, a runtime secret lookup tool constrained by configuration, plus optional SDK `ShellTool` when configured.
- `ShellCommandExecutor`: Executes SDK `ShellTool` command requests with configured `allowlist` or explicit `allow_all` command policy.
- `ToolExecutor`: Compatibility adapter for direct tests and diagnostics; routes `ToolCall` requests to CLI or file operation backends and returns normalized `ToolResult` objects.

## Internal Structure

- `__init__.py`: Public exports only.
- `_registry.py`: Capability discovery and lookup.
- `_agents_tools.py`: OpenAI Agents SDK function tool construction for configured local tools and user-visible progress events.
- `_tool_artifacts.py`: Per-run local tool output artifact persistence plus bounded artifact search and slice helpers.
- `_shell_executor.py`: Local SDK `ShellTool` executor with command policy enforcement and timeout handling.
- `_cli_runner.py`: Async subprocess execution and command allowlisting.
- `_file_ops.py`: Scoped file operations.
- `_executor.py`: Tool routing and normalized result handling.
- `SPEC.md`: Module design.

## Error Handling

Tool failures are surfaced according to the tool mode. During SDK-managed runs, recoverable local function tool failures return model-visible error text so the agent can retry or report failure. Invalid configuration, timeout exhaustion, invalid tool names, malformed outputs, and shell policy violations raise `ToolExecutionError` from `models`.

## Design Decisions

- The OpenAI Agents SDK runner sees SDK tool objects; diagnostics and CLI `capabilities` see serializable `ToolDefinition` metadata.
- SDK-managed local tools emit live `RunEvent` values for start, completion, and failure when a run event sink is provided.
- Local tool events include structured payload metadata identifying the tool origin as `local`, allowing reports to distinguish real local utility calls from harness calls and runtime-only records.
- SDK-managed local tools write complete model-facing raw results to per-run artifacts when artifact output is enabled. Small and moderate current outputs are still returned inline to reduce extra model/tool turns; oversized outputs return an artifact reference, preview, and instructions to use `search_artifact` or `read_artifact_slice` only when more detail is needed.
- Artifact read tools only resolve paths inside the current run directory and enforce bounded search/slice results so artifact recovery cannot reintroduce unbounded context growth.
- A `publish_progress` SDK function tool lets the agent report planning, reasoning summaries, and plan updates in a user-visible way without exposing hidden chain-of-thought.
- A `wait_ms` SDK function tool provides pure elapsed-time waits for FSQ pause semantics and page-load delays. It must be preferred over platform gestures when the intended action is waiting, because gestures can alter scroll position or UI state.
- A `submit_visual_assertion` SDK function tool lets the agent bind one screenshot path to one visual assertion prompt, such as FSQ `assertWithAI`. The tool itself records the semantic assertion request; the agent runtime is responsible for attaching the image to the next model call when the path is readable under the configured output root.
- A `get_runtime_secret` SDK function tool reads only environment variable names listed in `runtime_secrets.allowed_env_names`. It is intended for setup flows such as account sign-in where credentials must stay out of FSQ YAML and source code. The tool returns the value to the model for immediate use, but user-visible events, artifact records, and report previews must redact secret values and should show only the variable name and presence status.
- CLI execution is allowlisted through configuration to avoid arbitrary command execution by default. Configured CLI tools run from the fsq-agent workspace so relative side effects do not land in the user's current directory.
- File operation tools treat `cases.dir` as read-only input and write generated files only under the output root.
- Skills remain descriptive instruction files. If shell is enabled, file-backed skills are attached to the SDK `ShellTool` local environment as skill metadata, while command execution is governed by `ShellSettings`.
- `shell.mode: allow_all` is supported for intentionally unrestricted local runs and should be treated as a high-trust mode.
- Platform action execution is outside the `tools` module. The active harness exposes platform action schemas, and the `agent` module adapts those schemas to SDK `FunctionTool` objects.
- Setup, teardown, app lifecycle, and observation behavior belong to harnesses, drivers, or explicit authored actions rather than to a tools-layer lifecycle controller.
