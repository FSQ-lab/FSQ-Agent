from pathlib import Path
from types import SimpleNamespace
from typing import Any

import json

import pytest

from fsq_agent.models import (
    MCPServerConfig,
    MCPToolValidationSettings,
    LocalToolOutputSettings,
    RunEvent,
    RuntimeSecretSettings,
    ShellSettings,
    SkillBundle,
    Task,
    ToolCall,
    ToolDefinition,
    ToolExecutionError,
)
from fsq_agent.tools import (
    AgentsMCPFactory,
    AgentsToolFactory,
    AppiumAndroidLifecycleController,
    CLIRunner,
    CapabilityRegistry,
    FileOps,
    LifecycleControllerFactory,
    MCPToolCaller,
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


class _FakeCallableMCPServer:
    name = "appium-mcp"

    def __init__(self, env: dict[str, str] | None = None, failures: list[tuple[str, str]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.failures = failures or []
        self.params = SimpleNamespace(env=env or {})

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((tool_name, arguments))
        if self.failures and self.failures[0][0] == tool_name:
            _, message = self.failures.pop(0)
            return type("ToolResult", (), {"content": [type("Text", (), {"text": message})()], "isError": True})()
        if tool_name == "appium_session_management" and arguments.get("action") == "create":
            return type("ToolResult", (), {"content": [type("Text", (), {"text": "ANDROID session created successfully with ID: session-1"})()], "isError": False})()
        return type("ToolResult", (), {"content": [type("Text", (), {"text": "ok"})()], "isError": False})()


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


@pytest.mark.asyncio
async def test_agents_tool_factory_publish_progress_emits_event(tmp_path: Path) -> None:
    events: list[RunEvent] = []
    factory = AgentsToolFactory(CLIRunner([]), FileOps(tmp_path))
    factory.build_tools(run_id="run-1", task_id="task-1", event_sink=events.append)

    output = await factory._publish_progress(
        None,
        '{"kind":"planning_update","message":"Checking current screen.","next_action":"Open menu."}',
    )

    assert output == '{"ok": true}'
    assert events[0].type == "planning_update"
    assert events[0].message == "Checking current screen. Next: Open menu."


@pytest.mark.asyncio
async def test_agents_tool_factory_submit_visual_assertion_returns_semantic_request_without_duplicate_events(tmp_path: Path) -> None:
    events: list[RunEvent] = []
    factory = AgentsToolFactory(CLIRunner([]), FileOps(tmp_path))
    tools = factory.build_tools(run_id="run-1", task_id="task-1", event_sink=events.append)

    output = await factory._submit_visual_assertion(
        None,
        json.dumps(
            {
                "assertion_id": "key-action-7",
                "prompt": "Verify the page layout.",
                "screenshot_path": "C:/tmp/screenshot.png",
            }
        ),
    )

    assert any(getattr(tool, "name", None) == "submit_visual_assertion" for tool in tools)
    payload = json.loads(output)
    assert payload["type"] == "visual_assertion_submission"
    assert payload["assertion_id"] == "key-action-7"
    assert payload["prompt"] == "Verify the page layout."
    assert payload["screenshot_path"] == "C:/tmp/screenshot.png"
    assert events == []


@pytest.mark.asyncio
async def test_agents_tool_factory_wait_ms_returns_pure_wait_result(tmp_path: Path) -> None:
    factory = AgentsToolFactory(CLIRunner([]), FileOps(tmp_path))
    tools = factory.build_tools(run_id="run-1", task_id="task-1")

    output = await factory._wait_ms(None, json.dumps({"duration_ms": 1, "reason": "page-load pause"}))

    assert any(getattr(tool, "name", None) == "wait_ms" for tool in tools)
    payload = json.loads(output)
    assert payload["type"] == "wait_completed"
    assert payload["duration_ms"] == 1
    assert payload["elapsed_ms"] >= 0
    assert payload["reason"] == "page-load pause"


@pytest.mark.asyncio
async def test_agents_tool_factory_runtime_secret_is_allowlisted_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "secret-password")
    events: list[RunEvent] = []
    factory = AgentsToolFactory(
        CLIRunner([]),
        FileOps(tmp_path),
        runtime_secret_settings=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
    )
    tools = factory.build_tools(run_id="run-1", task_id="task-1", event_sink=events.append)

    output = await factory._get_runtime_secret(None, json.dumps({"name": "TEST_ACCOUNT_PASSWORD"}))

    assert any(getattr(tool, "name", None) == "get_runtime_secret" for tool in tools)
    payload = json.loads(output)
    assert payload["value"] == "secret-password"
    assert payload["sensitive"] is True
    completed_event = events[-1]
    assert completed_event.type == "tool_call_completed"
    assert "secret-password" not in completed_event.tool_output_preview
    assert '"value": "***"' in completed_event.tool_output_preview


@pytest.mark.asyncio
async def test_agents_tool_factory_runtime_secret_rejects_unlisted_name(tmp_path: Path) -> None:
    factory = AgentsToolFactory(CLIRunner([]), FileOps(tmp_path), runtime_secret_settings=RuntimeSecretSettings())

    with pytest.raises(ToolExecutionError, match="not allowed"):
        await factory._get_runtime_secret(None, json.dumps({"name": "TEST_ACCOUNT_PASSWORD"}))


def test_agents_tool_factory_writes_full_output_artifact_and_returns_inline(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    factory = AgentsToolFactory(
        CLIRunner([]),
        FileOps(tmp_path),
        local_tool_output_settings=LocalToolOutputSettings(full_output_max_chars=1000),
        runs_dir=runs_dir,
    )
    factory.build_tools(run_id="run-1", task_id="task-1")

    output = factory._format_tool_response(
        "read_file",
        {"tool_name": "read_file", "status": "success", "output": "hello"},
        {"path": "file.txt"},
    )

    payload = json.loads(output)
    artifact_path = Path(payload["artifact"]["path"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["model_output"] == "full"
    assert payload["result"]["output"] == "hello"
    assert artifact["metadata"] == {"path": "file.txt"}
    assert '"output": "hello"' in artifact["content"]


@pytest.mark.asyncio
async def test_agents_tool_factory_large_output_uses_artifact_search_and_slice(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    factory = AgentsToolFactory(
        CLIRunner([]),
        FileOps(tmp_path),
        local_tool_output_settings=LocalToolOutputSettings(
            full_output_max_chars=50,
            historical_preview_chars=20,
            model_response_max_chars=500,
        ),
        runs_dir=runs_dir,
    )
    factory.build_tools(run_id="run-1", task_id="task-1")

    output = factory._format_tool_response(
        "read_file",
        {"tool_name": "read_file", "status": "success", "output": "alpha beta gamma " * 20},
        {"path": "large.txt"},
    )
    payload = json.loads(output)

    assert payload["model_output"] == "artifact_reference"
    assert "result" not in payload
    search_output = await factory._search_artifact(
        None,
        json.dumps({"artifact_path": payload["artifact"]["path"], "query": "gamma"}),
    )
    search_payload = json.loads(search_output)
    assert search_payload["matches"][0]["offset"] >= 0

    slice_output = await factory._read_artifact_slice(
        None,
        json.dumps(
            {
                "artifact_path": payload["artifact"]["path"],
                "offset": search_payload["matches"][0]["offset"],
                "length": 30,
            }
        ),
    )
    assert "gamma" in json.loads(slice_output)["content"]


def test_agents_mcp_factory_applies_client_session_timeout() -> None:
    config = MCPServerConfig(name="browser", command="npx", timeout_seconds=42)
    server = AgentsMCPFactory([config])._build_local_server(config)

    assert server.client_session_timeout_seconds == 42.0


def test_lifecycle_controller_factory_resolves_appium_android() -> None:
    from fsq_agent.models import LifecycleControllerSettings

    controller = LifecycleControllerFactory.create(
        LifecycleControllerSettings(controller="appium_android", options={})
    )

    assert isinstance(controller, AppiumAndroidLifecycleController)


@pytest.mark.asyncio
async def test_appium_android_lifecycle_calls_expected_tools(tmp_path: Path) -> None:
    capabilities_path = tmp_path / "capabilities.json"
    capabilities_path.write_text(json.dumps({"android": {"appium:appPackage": "com.example.app"}}), encoding="utf-8")
    server = _FakeCallableMCPServer({"CAPABILITIES_CONFIG": str(capabilities_path)})
    caller = MCPToolCaller([server], "run-1", "task-1")
    controller = AppiumAndroidLifecycleController()

    await controller.batch_setup(caller)
    assert controller.runtime_policy()[0] == "The runtime has already created exactly one Appium Android session for this MCP client. Because the strict Appium MCP tool schema requires sessionId, use sessionId 'session-1' on every appium-mcp tool call that accepts sessionId."
    await controller.case_setup(caller, Task(description="Run case."))
    await controller.case_teardown(caller, Task(description="Run case."))
    await controller.batch_teardown(caller)

    terminate_args = {
        "action": "terminate",
        "id": "com.example.app",
        "name": "",
        "path": "",
        "keepData": False,
        "applicationType": "User",
        "seconds": 5,
        "url": "",
        "waitForLaunch": True,
        "sessionId": "session-1",
    }
    activate_args = {**terminate_args, "action": "activate"}
    query_state_args = {**terminate_args, "action": "query_state"}
    assert server.calls == [
        ("appium_session_management", {"action": "create", "platform": "android"}),
        ("appium_session_management", {"action": "list"}),
        ("appium_app_lifecycle", terminate_args),
        ("appium_app_lifecycle", activate_args),
        ("appium_app_lifecycle", query_state_args),
        ("appium_mobile_keyboard", {"action": "hide", "keys": [], "sessionId": "session-1"}),
        ("appium_alert", {"action": "dismiss", "buttonLabel": "", "sessionId": "session-1"}),
        ("appium_app_lifecycle", terminate_args),
        ("appium_session_management", {"action": "delete"}),
        ("appium_session_management", {"action": "list"}),
    ]


@pytest.mark.asyncio
async def test_appium_android_lifecycle_retries_session_create(tmp_path: Path) -> None:
    capabilities_path = tmp_path / "capabilities.json"
    capabilities_path.write_text(json.dumps({"android": {"appium:appPackage": "com.example.app"}}), encoding="utf-8")
    server = _FakeCallableMCPServer(
        {"CAPABILITIES_CONFIG": str(capabilities_path)},
        failures=[("appium_session_management", "Appium Settings app is not running after 5000ms")],
    )
    caller = MCPToolCaller([server], "run-1", "task-1")
    controller = AppiumAndroidLifecycleController(session_create_retry_delay_seconds=0)

    await controller.batch_setup(caller)

    assert server.calls[:3] == [
        ("appium_session_management", {"action": "create", "platform": "android"}),
        ("appium_session_management", {"action": "create", "platform": "android"}),
        ("appium_session_management", {"action": "list"}),
    ]


@pytest.mark.asyncio
async def test_appium_android_case_setup_requires_app_package(tmp_path: Path) -> None:
    capabilities_path = tmp_path / "capabilities.json"
    capabilities_path.write_text(json.dumps({"android": {"appium:udid": "device-1"}}), encoding="utf-8")
    server = _FakeCallableMCPServer({"CAPABILITIES_CONFIG": str(capabilities_path)})
    caller = MCPToolCaller([server], "run-1", "task-1")
    controller = AppiumAndroidLifecycleController()

    await controller.batch_setup(caller)

    with pytest.raises(ToolExecutionError, match="appium:appPackage"):
        await controller.case_setup(caller, Task(description="Run case."))


@pytest.mark.asyncio
async def test_mcp_tool_caller_emits_lifecycle_events() -> None:
    events: list[RunEvent] = []
    server = _FakeCallableMCPServer()
    caller = MCPToolCaller([server], "run-1", "task-1", events.append)

    await caller.call("appium-mcp", "appium_session_management", {"action": "list"})

    assert [event.type for event in events] == ["tool_call_started", "tool_call_completed"]
    assert events[0].payload["lifecycle"] is True
    assert events[0].payload["tool_origin"] == "mcp"


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
