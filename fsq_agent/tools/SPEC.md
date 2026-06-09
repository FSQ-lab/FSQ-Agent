# Module: tools

## Purpose

Expose configured local capabilities as OpenAI Agents SDK tools, adapt MCP server configuration into SDK MCP integrations, and provide harness/platform adapters for platform automation. The OpenAI Agents SDK runner owns the model tool loop; this module owns local command/file safety, runtime secret access controls, MCP tool compatibility filtering, SDK tool construction, harness lifecycle sequencing, platform action registration, and platform action invocation.

## Dependencies

- `models`: Uses `ToolDefinition`, `ToolCall`, `ToolResult`, `MCPServerConfig`, `MCPToolValidationSettings`, `MCPToolValidationIssue`, `HarnessSettings`, `PlatformActionDefinition`, `PlatformActionResult`, `PlatformFailureCategory`, `CLIToolConfig`, `ShellSettings`, `RuntimeSecretSettings`, `SkillBundle`, `Task`, `RunEvent`, and `ToolExecutionError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `CapabilityRegistry`: Maintains discovered MCP, CLI, and file operation capabilities.
- `AgentsMCPFactory`: Builds OpenAI Agents SDK MCP server/tool objects from `MCPServerConfig` values, validates discovered local MCP tool schemas, applies manual and automatic tool filters, and exposes validation diagnostics from the latest run.
- `MCPToolValidator`: Validates local MCP tool schemas against the project's configured strict OpenAI tool schema compatibility policy.
- `CLIRunner`: Executes configured CLI commands asynchronously with timeout, output capture, and a configured workspace current working directory.
- `FileOps`: Performs scoped file reads and writes. Read roots include configured case, knowledge, and output directories; writes are restricted to the configured output root.
- `AgentsToolFactory`: Builds OpenAI Agents SDK `FunctionTool` objects for CLI and file operations, artifact search/slice operations, a progress publication tool for user-visible planning updates, a pure wait tool, an explicit visual assertion submission tool, a runtime secret lookup tool constrained by configuration, agent-visible platform actions supplied by the active harness, plus optional SDK `ShellTool` when configured.
- `Harness`: Abstract test-runtime facade that exposes platform action space, wraps action invocation with `before_action` and `after_action`, owns run/case setup and teardown hooks, and provides runtime policy text.
- `HarnessFactory`: Resolves `HarnessSettings` to a concrete harness implementation.
- `PlatformAdapter`: Abstract platform-operation engine that registers platform action definitions and executes concrete platform actions behind the harness.
- `NoopHarness`: Default harness that exposes no platform actions and performs no setup or teardown.
- `AndroidHarness`: Android test-runtime harness that owns Android run/case lifecycle policy and delegates platform operations to an Android platform adapter.
- `AndroidAppiumPlatformAdapter`: Android Appium platform adapter that registers Android action definitions, keeps session/app lifecycle capabilities lifecycle-only, reads platform capabilities from the configured capabilities source, and may temporarily hide backend transport details behind the adapter.
- `ShellCommandExecutor`: Executes SDK `ShellTool` command requests with configured `allowlist` or explicit `allow_all` command policy.
- `ToolExecutor`: Compatibility adapter for direct tests and diagnostics; routes `ToolCall` requests to CLI or file operation backends and returns normalized `ToolResult` objects. MCP execution is SDK-only.

## Internal Structure

- `__init__.py`: Public exports only.
- `_registry.py`: Capability discovery and lookup.
- `_agents_mcp.py`: OpenAI Agents SDK MCP server construction for stdio, Streamable HTTP, SSE, and hosted MCP.
- `_mcp_tool_validator.py`: Startup-time MCP tool schema compatibility validation and automatic ignore issue generation.
- `_agents_tools.py`: OpenAI Agents SDK function tool construction for configured local tools, harness-supplied platform actions, and user-visible progress events.
- `_harness.py`: Harness interface, harness factory, no-op harness, and shared harness invocation helpers.
- `_platform.py`: Platform adapter interface and shared platform action helpers.
- `_android_harness.py`: Android harness and Android Appium platform adapter.
- `_tool_artifacts.py`: Per-run local tool output artifact persistence plus bounded artifact search and slice helpers.
- `_shell_executor.py`: Local SDK `ShellTool` executor with command policy enforcement and timeout handling.
- `_cli_runner.py`: Async subprocess execution and command allowlisting.
- `_file_ops.py`: Scoped file operations.
- `_executor.py`: Tool routing and normalized result handling.
- `SPEC.md`: Module design.

## Error Handling

Tool and platform-action failures are surfaced according to the tool mode. During SDK-managed runs, recoverable function tool failures return model-visible error text so the agent can retry or report failure. Invalid configuration, timeout exhaustion, invalid tool names, unsupported platform actions, malformed outputs, shell policy violations, MCP construction errors, `fail_fast` MCP validation failures, and fatal harness lifecycle failures raise `ToolExecutionError` from `models` or are normalized into `PlatformActionResult` failures as appropriate for the caller.

## Design Decisions

- The OpenAI Agents SDK runner sees SDK tool objects; diagnostics and CLI `capabilities` see serializable `ToolDefinition` metadata.
- SDK-managed local tools and harness platform actions emit live `RunEvent` values for start, completion, and failure when a run event sink is provided. MCP tool execution remains SDK-owned when non-platform MCP integrations are configured and is observed through SDK stream events.
- Local tool events include structured payload metadata identifying the tool origin as `local`, allowing reports to distinguish real local tool calls from MCP/hosted calls and runtime-only records.
- SDK-managed local tools and harness platform actions write complete model-facing raw results to per-run artifacts when artifact output is enabled. Small and moderate current outputs are still returned inline to reduce extra model/tool turns; oversized outputs return an artifact reference, preview, and instructions to use `search_artifact` or `read_artifact_slice` only when more detail is needed.
- Artifact read tools only resolve paths inside the current run directory and enforce bounded search/slice results so artifact recovery cannot reintroduce unbounded context growth.
- A `publish_progress` SDK function tool lets the agent report planning, reasoning summaries, and plan updates in a user-visible way without exposing hidden chain-of-thought.
- A `wait_ms` SDK function tool provides pure elapsed-time waits for FSQ pause semantics and page-load delays. It must be preferred over Appium gestures when the intended action is waiting, because gestures can alter scroll position or UI state.
- A `submit_visual_assertion` SDK function tool lets the agent bind one screenshot path to one visual assertion prompt, such as FSQ `assertWithAI`. The tool itself records the semantic assertion request; the agent runtime is responsible for attaching the image to the next model call when the path is readable under the configured output root.
- A `get_runtime_secret` SDK function tool reads only environment variable names listed in `runtime_secrets.allowed_env_names`. It is intended for setup flows such as account sign-in where credentials must stay out of FSQ YAML and source code. The tool returns the value to the model for immediate use, but user-visible events, artifact records, and report previews must redact secret values and should show only the variable name and presence status.
- CLI execution is allowlisted through configuration to avoid arbitrary command execution by default. Configured CLI tools run from the fsq-agent workspace so relative side effects do not land in the user's current directory.
- File operation tools treat `cases.dir` as read-only input and write generated files only under the output root.
- Skills remain descriptive instruction files. If shell is enabled, file-backed skills are attached to the SDK `ShellTool` local environment as skill metadata, while command execution is governed by `ShellSettings`.
- `shell.mode: allow_all` is supported for intentionally unrestricted local runs and should be treated as a high-trust mode.
- MCP connection lifecycle is delegated to OpenAI Agents SDK context managers and server manager objects for non-platform MCP integrations. Platform action execution must not depend on user-configured backend server settings.
- Direct MCP tool calls are intentionally not supported by `ToolExecutor`. If a temporary platform adapter uses an MCP-backed implementation internally, that backend is hidden behind the adapter and must not leak into harness configuration, agent-visible action names, or StepRunner contracts.
- Harnesses own required baseline setup and teardown outside model reasoning. Platform operations needed for setup and teardown are registered by the platform adapter with `lifecycle_only` visibility so they are available to the harness but not exposed to the LLM.
- `AndroidHarness` owns Android run/case lifecycle policy. `AndroidAppiumPlatformAdapter` owns Android Appium action definitions, reads device/app capabilities such as `appium:udid` and `appium:appPackage` only from the capabilities file pointed to by the environment variable named in `harness.platform.capabilities_config_env`, registers session and app lifecycle operations as lifecycle-only capabilities, registers user-facing Android actions as agent-visible or runner-visible actions, and normalizes backend results into `PlatformActionResult`. Agent-visible Android actions must preserve the useful semantic shape of the hidden Appium backend without exposing MCP: precise locator fields (`strategy` and `selector`), direct `element_id` reuse, scroll-to-element, element text/attribute reads, bounded page source, window size, screenshot, tap, drag-and-drop, context list/switch, device info, text input, key press, back, and wait. Agent-visible tap must be element/locator based and must not expose coordinate fields; any backend coordinate fallback is compatibility-only and must lose to an element reference when both are supplied. Page source output must be bounded and hard-capped. Session identifiers and backend operation details are diagnostic-only and must not be injected as model-facing operating policy.
- MCP approval policy defaults to non-interactive trusted execution (`never`) unless the configuration explicitly supplies a programmatic callback strategy.
- Local MCP servers are connected, listed, and filtered before agent construction. Manual `allowed_tools` and `blocked_tools` are combined with automatically detected invalid tools, then applied through the OpenAI Agents SDK static tool filter.
- `MCPToolValidationSettings.strict_schema` is shared with the agent runtime: when enabled, tools validates schemas against strict OpenAI compatibility rules, and agent construction asks the OpenAI Agents SDK to convert MCP schemas to strict mode; when disabled, both strict behaviors are skipped.
- Automatic MCP tool validation is startup-only. The project does not retry a failed provider registration by mutating filters mid-run.
