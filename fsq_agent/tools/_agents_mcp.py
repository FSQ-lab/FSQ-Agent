from contextlib import AsyncExitStack
from typing import Any

from fsq_agent.models import (
    MCPServerConfig,
    MCPToolValidationIssue,
    MCPToolValidationSettings,
    ToolExecutionError,
)
from fsq_agent.tools._mcp_tool_validator import MCPToolValidator


class AgentsMCPFactory:
    def __init__(
        self,
        configs: list[MCPServerConfig],
        validation_settings: MCPToolValidationSettings | None = None,
    ) -> None:
        self.configs = configs
        self.validation_settings = validation_settings or MCPToolValidationSettings()
        self.validator = MCPToolValidator(self.validation_settings)
        self.validation_issues: list[MCPToolValidationIssue] = []

    async def enter_servers(self, stack: AsyncExitStack) -> tuple[list[Any], list[Any]]:
        mcp_servers: list[Any] = []
        hosted_tools: list[Any] = []
        self.validation_issues = []
        for config in self.configs:
            if config.transport == "hosted":
                hosted_tools.append(self._build_hosted_tool(config))
                continue
            server = self._build_local_server(config)
            entered_server = await stack.enter_async_context(server)
            await self._validate_and_filter_tools(entered_server, config)
            mcp_servers.append(entered_server)
        return mcp_servers, hosted_tools

    def get_validation_issues(self) -> list[MCPToolValidationIssue]:
        return list(self.validation_issues)

    def _build_hosted_tool(self, config: MCPServerConfig) -> Any:
        try:
            from agents import HostedMCPTool
        except ImportError as exc:
            raise ToolExecutionError("openai-agents is required for hosted MCP tools.") from exc
        if not config.url:
            raise ToolExecutionError("Hosted MCP server requires a URL.", context={"server": config.name})
        tool_config: dict[str, Any] = {
            "type": "mcp",
            "server_label": config.name,
            "server_url": config.url,
            "require_approval": config.require_approval,
        }
        if config.headers:
            tool_config["headers"] = config.headers
        return HostedMCPTool(tool_config=tool_config)

    def _build_local_server(self, config: MCPServerConfig) -> Any:
        try:
            from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp, create_static_tool_filter
        except ImportError as exc:
            raise ToolExecutionError("openai-agents is required for MCP server integration.") from exc

        common: dict[str, Any] = {
            "name": config.name,
            "cache_tools_list": config.cache_tools_list,
            "require_approval": config.require_approval,
            "tool_filter": None,
        }
        if config.timeout_seconds:
            common["client_session_timeout_seconds"] = float(config.timeout_seconds)
        if config.transport == "stdio":
            if not config.command:
                raise ToolExecutionError("stdio MCP server requires a command.", context={"server": config.name})
            params: dict[str, Any] = {"command": config.command, "args": config.args, "env": config.env}
            if config.cwd:
                params["cwd"] = str(config.cwd)
            return MCPServerStdio(params=params, **common)
        if not config.url:
            raise ToolExecutionError("HTTP MCP server requires a URL.", context={"server": config.name})
        params = {"url": config.url, "headers": config.headers}
        if config.timeout_seconds:
            params["timeout"] = config.timeout_seconds
        if config.transport == "streamable_http":
            return MCPServerStreamableHttp(params=params, **common)
        return MCPServerSse(params=params, **common)

    async def _validate_and_filter_tools(self, server: Any, config: MCPServerConfig) -> None:
        try:
            from agents.mcp import create_static_tool_filter
        except ImportError as exc:
            raise ToolExecutionError("openai-agents is required for MCP server integration.") from exc

        tools = await server.list_tools()
        issues = self.validator.validate_tools(config.name, tools)
        self.validation_issues.extend(issues)
        auto_blocked = {issue.tool_name for issue in issues if issue.policy == "auto_ignore"}
        effective_blocked = sorted(set(config.blocked_tools) | auto_blocked)
        server.tool_filter = create_static_tool_filter(
            allowed_tool_names=config.allowed_tools or None,
            blocked_tool_names=effective_blocked or None,
        )
        if self.validation_settings.fail_when_all_tools_filtered:
            remaining_tools = await server.list_tools()
            if tools and not remaining_tools:
                raise ToolExecutionError(
                    "All MCP tools were filtered out.",
                    context={
                        "server": config.name,
                        "manual_blocked_tools": config.blocked_tools,
                        "auto_blocked_tools": sorted(auto_blocked),
                        "allowed_tools": config.allowed_tools,
                    },
                )
