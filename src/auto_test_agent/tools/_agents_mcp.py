from contextlib import AsyncExitStack
from typing import Any

from auto_test_agent.models import MCPServerConfig, ToolExecutionError


class AgentsMCPFactory:
    def __init__(self, configs: list[MCPServerConfig]) -> None:
        self.configs = configs

    async def enter_servers(self, stack: AsyncExitStack) -> tuple[list[Any], list[Any]]:
        mcp_servers: list[Any] = []
        hosted_tools: list[Any] = []
        for config in self.configs:
            if config.transport == "hosted":
                hosted_tools.append(self._build_hosted_tool(config))
                continue
            server = self._build_local_server(config)
            mcp_servers.append(await stack.enter_async_context(server))
        return mcp_servers, hosted_tools

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

        tool_filter = None
        if config.allowed_tools or config.blocked_tools:
            tool_filter = create_static_tool_filter(
                allowed_tool_names=config.allowed_tools or None,
                blocked_tool_names=config.blocked_tools or None,
            )
        common: dict[str, Any] = {
            "name": config.name,
            "cache_tools_list": config.cache_tools_list,
            "require_approval": config.require_approval,
            "tool_filter": tool_filter,
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