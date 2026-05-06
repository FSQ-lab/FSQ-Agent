from pathlib import Path

import pytest

from auto_test_agent.models import MCPServerConfig, ShellSettings, SkillBundle, ToolCall, ToolDefinition, ToolExecutionError
from auto_test_agent.tools import AgentsMCPFactory, AgentsToolFactory, CLIRunner, CapabilityRegistry, FileOps, ToolExecutor


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