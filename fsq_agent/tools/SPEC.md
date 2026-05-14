# Module: tools

## Purpose

Expose configured local capabilities as OpenAI Agents SDK tools, adapt MCP server configuration into SDK MCP integrations, and provide controlled setup/teardown lifecycle controllers for platform-specific MCP workflows. The OpenAI Agents SDK runner owns the model tool loop; this module owns local command/file safety, MCP tool compatibility filtering, SDK tool construction, and deterministic lifecycle MCP calls.

## Dependencies

- `models`: Uses `ToolDefinition`, `ToolCall`, `ToolResult`, `MCPServerConfig`, `MCPToolValidationSettings`, `MCPToolValidationIssue`, `LifecycleControllerSettings`, `CLIToolConfig`, `ShellSettings`, `SkillBundle`, `Task`, `RunEvent`, and `ToolExecutionError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `CapabilityRegistry`: Maintains discovered MCP, CLI, and file operation capabilities.
- `AgentsMCPFactory`: Builds OpenAI Agents SDK MCP server/tool objects from `MCPServerConfig` values, validates discovered local MCP tool schemas, applies manual and automatic tool filters, and exposes validation diagnostics from the latest run.
- `MCPToolValidator`: Validates local MCP tool schemas against the project's configured strict OpenAI tool schema compatibility policy.
- `CLIRunner`: Executes configured CLI commands asynchronously with timeout, output capture, and a configured workspace current working directory.
- `FileOps`: Performs scoped file reads and writes. Read roots include configured case, knowledge, and output directories; writes are restricted to the configured output root.
- `AgentsToolFactory`: Builds OpenAI Agents SDK `FunctionTool` objects for CLI and file operations, artifact search/slice operations, a progress publication tool for user-visible planning updates, a pure wait tool, an explicit visual assertion submission tool, plus optional SDK `ShellTool` when configured.
- `LifecycleController`: Abstract setup/teardown interface with batch and case lifecycle methods.
- `LifecycleControllerFactory`: Resolves the configured lifecycle controller name to a concrete implementation.
- `MCPToolCaller`: Controlled direct MCP caller used only by lifecycle controllers after servers have been entered and validated.
- `NoopLifecycleController`: Default lifecycle controller that performs no setup or teardown.
- `AppiumAndroidLifecycleController`: Appium Android implementation that creates a session from the Appium capabilities configuration, validates it with `list`, restores the AUT around each case, and deletes the active session during teardown.
- `ShellCommandExecutor`: Executes SDK `ShellTool` command requests with configured `allowlist` or explicit `allow_all` command policy.
- `ToolExecutor`: Compatibility adapter for direct tests and diagnostics; routes `ToolCall` requests to CLI or file operation backends and returns normalized `ToolResult` objects. MCP execution is SDK-only.

## Internal Structure

- `__init__.py`: Public exports only.
- `_registry.py`: Capability discovery and lookup.
- `_agents_mcp.py`: OpenAI Agents SDK MCP server construction for stdio, Streamable HTTP, SSE, and hosted MCP.
- `_mcp_tool_validator.py`: Startup-time MCP tool schema compatibility validation and automatic ignore issue generation.
- `_agents_tools.py`: OpenAI Agents SDK function tool construction for configured local tools and user-visible progress events.
- `_lifecycle.py`: Lifecycle controller interface, controller registry, controlled MCP caller, no-op controller, and Appium Android controller.
- `_tool_artifacts.py`: Per-run local tool output artifact persistence plus bounded artifact search and slice helpers.
- `_shell_executor.py`: Local SDK `ShellTool` executor with command policy enforcement and timeout handling.
- `_cli_runner.py`: Async subprocess execution and command allowlisting.
- `_file_ops.py`: Scoped file operations.
- `_executor.py`: Tool routing and normalized result handling.
- `SPEC.md`: Module design.

## Error Handling

Tool failures are surfaced according to the tool mode. During SDK-managed runs, recoverable function tool failures return model-visible error text so the agent can retry or report failure. Invalid configuration, timeout exhaustion, invalid tool names, malformed outputs, shell policy violations, direct MCP calls, MCP construction errors, and `fail_fast` MCP validation failures raise `ToolExecutionError` from `models`.

## Design Decisions

- The OpenAI Agents SDK runner sees SDK tool objects; diagnostics and CLI `capabilities` see serializable `ToolDefinition` metadata.
- SDK-managed local tools emit live `RunEvent` values for start, completion, and failure when a run event sink is provided. MCP tool execution remains SDK-owned and is observed through SDK stream events.
- Local tool events include structured payload metadata identifying the tool origin as `local`, allowing reports to distinguish real local tool calls from MCP/hosted calls and runtime-only records.
- SDK-managed local tools write complete model-facing raw results to per-run artifacts when artifact output is enabled. Small and moderate current outputs are still returned inline to reduce extra model/tool turns; oversized outputs return an artifact reference, preview, and instructions to use `search_artifact` or `read_artifact_slice` only when more detail is needed.
- Artifact read tools only resolve paths inside the current run directory and enforce bounded search/slice results so artifact recovery cannot reintroduce unbounded context growth.
- A `publish_progress` SDK function tool lets the agent report planning, reasoning summaries, and plan updates in a user-visible way without exposing hidden chain-of-thought.
- A `wait_ms` SDK function tool provides pure elapsed-time waits for FSQ pause semantics and page-load delays. It must be preferred over Appium gestures when the intended action is waiting, because gestures can alter scroll position or UI state.
- A `submit_visual_assertion` SDK function tool lets the agent bind one screenshot path to one visual assertion prompt, such as FSQ `assertWithAI`. The tool itself records the semantic assertion request; the agent runtime is responsible for attaching the image to the next model call when the path is readable under the configured output root.
- CLI execution is allowlisted through configuration to avoid arbitrary command execution by default. Configured CLI tools run from the fsq-agent workspace so relative side effects do not land in the user's current directory.
- File operation tools treat `cases.dir` as read-only input and write generated files only under the output root.
- Skills remain descriptive instruction files. If shell is enabled, file-backed skills are attached to the SDK `ShellTool` local environment as skill metadata, while command execution is governed by `ShellSettings`.
- `shell.mode: allow_all` is supported for intentionally unrestricted local runs and should be treated as a high-trust mode.
- MCP connection lifecycle is delegated to OpenAI Agents SDK context managers and server manager objects. This module only translates project config into SDK objects.
- Direct MCP tool calls are intentionally not supported by `ToolExecutor`. The only non-agent MCP call path is `MCPToolCaller`, which is scoped to lifecycle controllers and can only call servers already entered by `AgentsMCPFactory`.
- Lifecycle controllers own the required baseline setup and teardown outside model reasoning. Scenario-useful lifecycle tools, such as Appium app lifecycle actions, may still be exposed to the agent through `allowed_tools`; session management remains runtime-owned unless explicitly configured otherwise.
- `AppiumAndroidLifecycleController` relies on `CAPABILITIES_CONFIG` for device/app capabilities such as `appium:udid` and `appium:appPackage`. Batch setup uses `appium_session_management` with `action=create`, parses the created session ID, then uses `action=list` as a diagnostic. Session creation is retried by the lifecycle controller because Android helper-app startup can fail transiently during cold starts. Official Appium MCP semantics allow omitted `sessionId` to use the single active session, but strict OpenAI Agents SDK MCP schema conversion can expose Appium tools that reject omitted `sessionId` as a missing required parameter and empty `sessionId` as an invalid explicit target. Therefore, the controller centralizes session ownership: it creates exactly one MCP-owned Appium session, injects the non-empty runtime session ID into model-visible policy, and passes it on lifecycle calls that accept `sessionId`. Case setup terminates the AUT if needed, activates it, and queries state. Case teardown hides the keyboard, dismisses alerts, and terminates the AUT with those cleanup failures treated as non-fatal. Batch teardown deletes the active session and attempts a non-fatal final `action=list` diagnostic.
- MCP approval policy defaults to non-interactive trusted execution (`never`) unless the configuration explicitly supplies a programmatic callback strategy.
- Local MCP servers are connected, listed, and filtered before agent construction. Manual `allowed_tools` and `blocked_tools` are combined with automatically detected invalid tools, then applied through the OpenAI Agents SDK static tool filter.
- `MCPToolValidationSettings.strict_schema` is shared with the agent runtime: when enabled, tools validates schemas against strict OpenAI compatibility rules, and agent construction asks the OpenAI Agents SDK to convert MCP schemas to strict mode; when disabled, both strict behaviors are skipped.
- Automatic MCP tool validation is startup-only. The project does not retry a failed provider registration by mutating filters mid-run.
