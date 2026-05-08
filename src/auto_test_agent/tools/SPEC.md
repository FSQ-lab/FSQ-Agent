# Module: tools

## Purpose

Expose configured local capabilities as OpenAI Agents SDK tools and adapt MCP server configuration into SDK MCP integrations. The OpenAI Agents SDK runner owns the model tool loop; this module owns local command/file safety, MCP tool compatibility filtering, and SDK tool construction.

## Dependencies

- `models`: Uses `ToolDefinition`, `ToolCall`, `ToolResult`, `MCPServerConfig`, `MCPToolValidationSettings`, `MCPToolValidationIssue`, `CLIToolConfig`, `ShellSettings`, `SkillBundle`, and `ToolExecutionError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `CapabilityRegistry`: Maintains discovered MCP, CLI, and file operation capabilities.
- `AgentsMCPFactory`: Builds OpenAI Agents SDK MCP server/tool objects from `MCPServerConfig` values, validates discovered local MCP tool schemas, applies manual and automatic tool filters, and exposes validation diagnostics from the latest run.
- `MCPToolValidator`: Validates local MCP tool schemas against the project's configured strict OpenAI tool schema compatibility policy.
- `CLIRunner`: Executes configured CLI commands asynchronously with timeout and output capture.
- `FileOps`: Performs scoped file reads and writes for task inputs, logs, and reports.
- `AgentsToolFactory`: Builds OpenAI Agents SDK `FunctionTool` objects for CLI and file operations, plus optional SDK `ShellTool` when configured.
- `ShellCommandExecutor`: Executes SDK `ShellTool` command requests with configured `allowlist` or explicit `allow_all` command policy.
- `ToolExecutor`: Compatibility adapter for direct tests and diagnostics; routes `ToolCall` requests to CLI or file operation backends and returns normalized `ToolResult` objects. MCP execution is SDK-only.

## Internal Structure

- `__init__.py`: Public exports only.
- `_registry.py`: Capability discovery and lookup.
- `_agents_mcp.py`: OpenAI Agents SDK MCP server construction for stdio, Streamable HTTP, SSE, and hosted MCP.
- `_mcp_tool_validator.py`: Startup-time MCP tool schema compatibility validation and automatic ignore issue generation.
- `_agents_tools.py`: OpenAI Agents SDK function tool construction for configured local tools.
- `_shell_executor.py`: Local SDK `ShellTool` executor with command policy enforcement and timeout handling.
- `_cli_runner.py`: Async subprocess execution and command allowlisting.
- `_file_ops.py`: Scoped file operations.
- `_executor.py`: Tool routing and normalized result handling.
- `SPEC.md`: Module design.

## Error Handling

Tool failures are surfaced according to the tool mode. During SDK-managed runs, recoverable function tool failures return model-visible error text so the agent can retry or report failure. Invalid configuration, timeout exhaustion, invalid tool names, malformed outputs, shell policy violations, direct MCP calls, MCP construction errors, and `fail_fast` MCP validation failures raise `ToolExecutionError` from `models`.

## Design Decisions

- The OpenAI Agents SDK runner sees SDK tool objects; diagnostics and CLI `capabilities` see serializable `ToolDefinition` metadata.
- CLI execution is allowlisted through configuration to avoid arbitrary command execution by default.
- Skills remain descriptive instruction files. If shell is enabled, file-backed skills are attached to the SDK `ShellTool` local environment as skill metadata, while command execution is governed by `ShellSettings`.
- `shell.mode: allow_all` is supported for intentionally unrestricted local runs and should be treated as a high-trust mode.
- MCP connection lifecycle is delegated to OpenAI Agents SDK context managers and server manager objects. This module only translates project config into SDK objects.
- Direct MCP tool calls are intentionally not supported by `ToolExecutor`; there is a single MCP execution path through OpenAI Agents SDK.
- MCP approval policy defaults to non-interactive trusted execution (`never`) unless the configuration explicitly supplies a programmatic callback strategy.
- Local MCP servers are connected, listed, and filtered before agent construction. Manual `allowed_tools` and `blocked_tools` are combined with automatically detected invalid tools, then applied through the OpenAI Agents SDK static tool filter.
- Automatic MCP tool validation is startup-only. The project does not retry a failed provider registration by mutating filters mid-run.
