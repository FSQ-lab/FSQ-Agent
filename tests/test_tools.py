from pathlib import Path
from typing import Any

import pytest

from auto_test_agent.models import (
    MCPServerConfig,
    MCPToolValidationSettings,
    ShellSettings,
    SkillBundle,
    ToolCall,
    ToolDefinition,
    ToolExecutionError,
)
from auto_test_agent.tools import (
    AgentsMCPFactory,
    AgentsToolFactory,
    CLIRunner,
    CapabilityRegistry,
    FileOps,
    MCPToolValidator,
    ToolExecutor,
)


class _FakeMCPTool:
    def __init__(self, name: str, input_schema: dict[str, Any]) -> None:
        self.name = name
        self.inputSchema = input_schema


class _FakeMCPServer:
    def __init__(self, tools: list[_FakeMCPTool]) -> None:
        self.tools = tools
        self.tool_filter: dict[str, list[str]] | None = None

    async def list_tools(self) -> list[_FakeMCPTool]:
        filtered_tools = self.tools
        if self.tool_filter:
            allowed = self.tool_filter.get("allowed_tool_names")
            blocked = self.tool_filter.get("blocked_tool_names")
            if allowed is not None:
                filtered_tools = [tool for tool in filtered_tools if tool.name in allowed]
            if blocked is not None:
                filtered_tools = [tool for tool in filtered_tools if tool.name not in blocked]
        return filtered_tools


@pytest.mark.asyncio
async def test_file_ops_are_scoped(tmp_path: Path) -> None:
    registry = CapabilityRegistry.from_cli_tools([])
    executor = ToolExecutor(registry, CLIRunner([]), FileOps(tmp_path))

    result = await executor.execute(
        ToolCall(tool_name="file.write", arguments={"path": "nested/out.txt", "content": "hello"})
    )

    assert result.status == "success"
    assert (tmp_path / "nested" / "out.txt").read_text(encoding="utf-8") == "hello"


@pytest.mark.asyncio
async def test_direct_mcp_execution_is_sdk_only(tmp_path: Path) -> None:
    registry = CapabilityRegistry.from_cli_tools([])
    registry.register(ToolDefinition(name="browser.click", kind="mcp", server_name="browser"))
    executor = ToolExecutor(registry, CLIRunner([]), FileOps(tmp_path))

    with pytest.raises(ToolExecutionError, match="OpenAI Agents SDK"):
        await executor.execute(ToolCall(tool_name="browser.click", arguments={}))


def test_agents_tool_factory_adds_shell_tool_with_file_backed_skill(tmp_path: Path) -> None:
    skill_file = tmp_path / "browser.md"
    skill_file.write_text("Use CLI commands only when configured.", encoding="utf-8")
    factory = AgentsToolFactory(
        CLIRunner([]),
        FileOps(tmp_path),
        ShellSettings(
            enabled=True,
            mode="allowlist",
            command_allowlist=["echo"],
            working_dir=tmp_path,
        ),
    )

    tools = factory.build_tools(
        [
            SkillBundle(
                name="browser-cli",
                description="Browser CLI usage guidance.",
                kind="markdown",
                instructions="Use echo for tests.",
                files=[skill_file],
            )
        ]
    )

    shell_tool = next(tool for tool in tools if getattr(tool, "name", None) == "shell")
    assert shell_tool.environment["type"] == "local"
    assert shell_tool.environment["skills"][0]["name"] == "browser-cli"
    assert shell_tool.environment["skills"][0]["path"] == str(skill_file)


def test_agents_mcp_factory_applies_client_session_timeout() -> None:
    config = MCPServerConfig(name="browser", command="npx", timeout_seconds=42)
    server = AgentsMCPFactory([config])._build_local_server(config)

    assert server.client_session_timeout_seconds == 42.0


def test_mcp_tool_validator_flags_unsupported_schema_keyword() -> None:
    validator = MCPToolValidator(MCPToolValidationSettings())
    tool = _FakeMCPTool(
        "bad_tool",
        {
            "type": "object",
            "properties": {},
            "propertyNames": {"pattern": "^[a-z]+$"},
        },
    )

    issues = validator.validate_tools("server", [tool])

    assert len(issues) == 1
    assert issues[0].tool_name == "bad_tool"
    assert "propertyNames" in issues[0].reason
    assert issues[0].schema_path == "$.propertyNames"


def test_mcp_tool_validator_fail_fast_raises() -> None:
    validator = MCPToolValidator(MCPToolValidationSettings(invalid_tool_policy="fail_fast"))
    tool = _FakeMCPTool("bad_tool", {"type": "object", "propertyNames": {}})

    with pytest.raises(ToolExecutionError, match="compatibility validation"):
        validator.validate_tools("server", [tool])


@pytest.mark.asyncio
async def test_agents_mcp_factory_auto_blocks_invalid_tools_and_preserves_manual_blocks() -> None:
    factory = AgentsMCPFactory([MCPServerConfig(name="server")], MCPToolValidationSettings())
    server = _FakeMCPServer(
        [
            _FakeMCPTool("healthy", {"type": "object", "properties": {}}),
            _FakeMCPTool("bad", {"type": "object", "propertyNames": {}}),
            _FakeMCPTool("manual", {"type": "object", "properties": {}}),
        ]
    )
    config = MCPServerConfig(name="server", blocked_tools=["manual"])

    await factory._validate_and_filter_tools(server, config)

    assert server.tool_filter == {"blocked_tool_names": ["bad", "manual"]}
    assert [tool.name for tool in await server.list_tools()] == ["healthy"]
    assert factory.get_validation_issues()[0].tool_name == "bad"


@pytest.mark.asyncio
async def test_agents_mcp_factory_raises_when_all_tools_are_filtered() -> None:
    factory = AgentsMCPFactory([MCPServerConfig(name="server")], MCPToolValidationSettings())
    server = _FakeMCPServer([_FakeMCPTool("bad", {"type": "object", "propertyNames": {}})])

    with pytest.raises(ToolExecutionError, match="All MCP tools were filtered out"):
        await factory._validate_and_filter_tools(server, MCPServerConfig(name="server"))
