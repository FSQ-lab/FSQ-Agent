from pathlib import Path
from types import SimpleNamespace
from typing import Any

import json

import pytest

from fsq_agent.models import (
    HarnessPlatformSettings,
    HarnessSettings,
    MCPServerConfig,
    MCPToolValidationSettings,
    LocalToolOutputSettings,
    PlatformActionDefinition,
    PlatformActionResult,
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
    AndroidAppiumPlatformAdapter,
    AndroidHarness,
    CLIRunner,
    CapabilityRegistry,
    FileOps,
    HarnessFactory,
    NoopHarness,
    MCPToolValidator,
    ToolExecutor,
)
from fsq_agent.tools._android_harness import AndroidAppiumMCPBackend


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
        if tool_name == "appium_find_element":
            return type("ToolResult", (), {"content": [type("Text", (), {"text": "elementId 'element-1'\nSuccessfully found element."})()], "isError": False})()
        if tool_name == "appium_get_page_source":
            return type("ToolResult", (), {"content": [type("Text", (), {"text": "<node text='Settings'/>" * 20})()], "isError": False})()
        if tool_name == "appium_screenshot":
            return type("ToolResult", (), {"content": [type("Text", (), {"text": "Screenshot saved successfully to: C:/tmp/screenshot.png"})()], "isError": False})()
        return type("ToolResult", (), {"content": [type("Text", (), {"text": "ok"})()], "isError": False})()


class _FakeAndroidBackend:
    def __init__(self, failures: list[tuple[str, str]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.failures = failures or []

    async def call(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((action_name, arguments))
        if self.failures and self.failures[0][0] == action_name:
            _, message = self.failures.pop(0)
            return {"ok": False, "error": message, "failure_category": "lifecycle_error"}
        if action_name == "android_create_session":
            return {"ok": True, "session_id": "session-1"}
        return {"ok": True}


class _FakeHarness:
    def __init__(self, result: PlatformActionResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def action_space(self, consumer: str = "agent") -> list[PlatformActionDefinition]:
        return [PlatformActionDefinition(name="android_page_source", input_schema={"type": "object", "properties": {}, "additionalProperties": False})]

    async def invoke_action(self, action_name: str, params: dict[str, Any]) -> PlatformActionResult:
        self.calls.append((action_name, params))
        return self.result


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


@pytest.mark.asyncio
async def test_agents_tool_factory_platform_action_large_output_uses_artifact_search_and_slice(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    harness = _FakeHarness(
        PlatformActionResult(
            action_name="android_page_source",
            status="success",
            output={"text": "alpha beta gamma " * 20},
        )
    )
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
    factory.build_tools(run_id="run-1", task_id="task-1", harness=harness)

    output = await factory._platform_action_tool(harness, "android_page_source")(None, json.dumps({"max_chars": 12000}))
    payload = json.loads(output)

    assert harness.calls == [("android_page_source", {"max_chars": 12000})]
    assert payload["tool_name"] == "android_page_source"
    assert payload["model_output"] == "artifact_reference"
    search_output = await factory._search_artifact(
        None,
        json.dumps({"artifact_path": payload["artifact"]["path"], "query": "gamma"}),
    )
    search_payload = json.loads(search_output)
    assert search_payload["matches"][0]["offset"] >= 0


def test_agents_mcp_factory_applies_client_session_timeout() -> None:
    config = MCPServerConfig(name="browser", command="npx", timeout_seconds=42)
    server = AgentsMCPFactory([config])._build_local_server(config)

    assert server.client_session_timeout_seconds == 42.0


def test_harness_factory_resolves_android() -> None:
    harness = HarnessFactory.create(
        HarnessSettings(name="android", platform=HarnessPlatformSettings(type="android", automation="appium"))
    )

    assert isinstance(harness, AndroidHarness)


def test_harness_factory_defaults_to_noop() -> None:
    harness = HarnessFactory.create(HarnessSettings())

    assert isinstance(harness, NoopHarness)


def test_agents_tool_factory_adds_agent_visible_platform_actions(tmp_path: Path) -> None:
    backend = _FakeAndroidBackend()
    adapter = AndroidAppiumPlatformAdapter(HarnessPlatformSettings(type="android", automation="appium"), backend=backend)
    harness = AndroidHarness(adapter)
    factory = AgentsToolFactory(CLIRunner([]), FileOps(tmp_path))

    tools = factory.build_tools(harness=harness)
    tool_names = {getattr(tool, "name", None) for tool in tools}

    assert "android_tap" in tool_names
    assert "android_scroll_to_element" in tool_names
    assert "android_drag_and_drop" in tool_names
    assert "android_get_attribute" in tool_names
    assert "android_page_source" in tool_names
    assert "android_screenshot" in tool_names
    assert "android_context" in tool_names
    assert "android_device_info" in tool_names
    assert "android_create_session" not in tool_names


def test_android_platform_action_schemas_expose_precise_locators() -> None:
    adapter = AndroidAppiumPlatformAdapter(HarnessPlatformSettings(type="android", automation="appium"), backend=_FakeAndroidBackend())

    tap_schema = adapter.action_definition("android_tap").input_schema
    assert set(tap_schema["properties"]).issuperset({"element_id", "strategy", "selector", "target"})
    assert "x" not in tap_schema["properties"]
    assert "y" not in tap_schema["properties"]
    assert "accessibility id" in tap_schema["properties"]["strategy"]["enum"]
    assert tap_schema["required"] == []
    assert adapter.action_definition("android_create_session").visibility == "lifecycle_only"
    assert adapter.action_definition("android_page_source").evidence_policy == "ui_tree"

    drag_schema = adapter.action_definition("android_drag_and_drop").input_schema
    assert set(drag_schema["properties"]).issuperset(
        {"source_element_id", "source_strategy", "source_selector", "source_target", "source_x", "source_y", "target_element_id", "target_strategy", "target_selector", "target_target", "target_x", "target_y"}
    )

    context_schema = adapter.action_definition("android_context").input_schema
    assert context_schema["properties"]["action"]["enum"] == ["list", "switch"]

    device_info_schema = adapter.action_definition("android_device_info").input_schema
    assert device_info_schema["properties"]["action"]["enum"] == ["info", "battery", "time"]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_creates_session() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)

    result = await backend.call("android_create_session", {"platform": "android"})

    assert result["ok"] is True
    assert result["session_id"] == "session-1"
    assert backend.session_id == "session-1"
    assert server.calls == [("appium_session_management", {"action": "create", "platform": "android"})]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_tap_finds_then_taps() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_tap", {"target": "accessibilityId=Login"})

    assert result["ok"] is True
    assert server.calls == [
        ("appium_find_element", {"strategy": "accessibility id", "selector": "Login", "sessionId": "session-1"}),
        ("appium_gesture", {"action": "tap", "elementUUID": "element-1", "sessionId": "session-1"}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_tap_accepts_direct_element_id() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_tap", {"target": "elementId 'element-1'"})

    assert result["ok"] is True
    assert server.calls == [
        ("appium_gesture", {"action": "tap", "elementUUID": "element-1", "sessionId": "session-1"}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_tap_accepts_precise_locator() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_tap", {"strategy": "id", "selector": "com.example:id/settings"})

    assert result["ok"] is True
    assert server.calls == [
        ("appium_find_element", {"strategy": "id", "selector": "com.example:id/settings", "sessionId": "session-1"}),
        ("appium_gesture", {"action": "tap", "elementUUID": "element-1", "sessionId": "session-1"}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_tap_prefers_element_over_coordinates() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_tap", {"element_id": "element-1", "x": 999999, "y": 999999})

    assert result["ok"] is True
    assert server.calls == [
        ("appium_gesture", {"action": "tap", "elementUUID": "element-1", "sessionId": "session-1"}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_scrolls_to_element_with_locator() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call(
        "android_scroll_to_element",
        {"strategy": "accessibility id", "selector": "Settings", "direction": "down", "max_scroll_attempts": 4},
    )

    assert result["ok"] is True
    assert server.calls == [
        (
            "appium_gesture",
            {
                "action": "scroll_to_element",
                "strategy": "accessibility id",
                "selector": "Settings",
                "direction": "down",
                "maxScrollAttempts": 4,
                "sessionId": "session-1",
            },
        )
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_get_attribute_accepts_direct_element_id() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_get_attribute", {"element_id": "element-1", "attribute": "displayed"})

    assert result["ok"] is True
    assert server.calls == [
        ("appium_get_element_attribute", {"elementUUID": "element-1", "attribute": "displayed", "sessionId": "session-1"}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_page_source_is_bounded() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_page_source", {"max_chars": 20})

    assert result["ok"] is True
    assert result["truncated"] is True
    assert len(result["text"]) == 20
    assert server.calls == [("appium_get_page_source", {"sessionId": "session-1"})]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_drag_and_drop_accepts_locators() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call(
        "android_drag_and_drop",
        {
            "source_strategy": "id",
            "source_selector": "com.example:id/source",
            "target_element_id": "target-1",
            "duration": 1200,
            "long_press_duration": 600,
        },
    )

    assert result["ok"] is True
    assert server.calls == [
        ("appium_find_element", {"strategy": "id", "selector": "com.example:id/source", "sessionId": "session-1"}),
        ("appium_drag_and_drop", {"sessionId": "session-1", "sourceElementUUID": "element-1", "targetElementUUID": "target-1", "duration": 1200, "longPressDuration": 600}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_drag_and_drop_accepts_coordinate_fallback() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    result = await backend.call("android_drag_and_drop", {"source_x": 10, "source_y": 20, "target_x": 30, "target_y": 40})

    assert result["ok"] is True
    assert server.calls == [
        ("appium_drag_and_drop", {"sessionId": "session-1", "sourceX": 10, "sourceY": 20, "targetX": 30, "targetY": 40}),
    ]


@pytest.mark.asyncio
async def test_android_appium_mcp_backend_context_and_device_info() -> None:
    server = _FakeCallableMCPServer()
    backend = AndroidAppiumMCPBackend(server)
    backend.session_id = "session-1"

    context_result = await backend.call("android_context", {"action": "switch", "context": "NATIVE_APP"})
    info_result = await backend.call("android_device_info", {"action": "time", "format": "YYYY"})

    assert context_result["ok"] is True
    assert info_result["ok"] is True
    assert server.calls == [
        ("appium_context", {"action": "switch", "sessionId": "session-1", "context": "NATIVE_APP"}),
        ("appium_mobile_device_info", {"action": "time", "sessionId": "session-1", "format": "YYYY"}),
    ]


@pytest.mark.asyncio
async def test_android_harness_calls_expected_lifecycle_actions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capabilities_path = tmp_path / "capabilities.json"
    capabilities_path.write_text(json.dumps({"android": {"appium:appPackage": "com.example.app"}}), encoding="utf-8")
    monkeypatch.setenv("CAPABILITIES_CONFIG", str(capabilities_path))
    backend = _FakeAndroidBackend()
    adapter = AndroidAppiumPlatformAdapter(HarnessPlatformSettings(type="android", automation="appium"), backend=backend)
    harness = AndroidHarness(adapter)

    await harness.run_setup()
    assert adapter.session_id == "session-1"
    assert "android_tap" in {definition.name for definition in harness.action_space("agent")}
    assert "android_create_session" not in {definition.name for definition in harness.action_space("agent")}
    await harness.case_setup(Task(description="Run case."))
    await harness.case_teardown(Task(description="Run case."))
    await harness.run_teardown()

    assert backend.calls == [
        ("android_create_session", {"platform": "android"}),
        ("android_terminate_app", {"app_id": "com.example.app"}),
        ("android_activate_app", {"app_id": "com.example.app"}),
        ("android_query_app_state", {"app_id": "com.example.app"}),
        ("android_hide_keyboard", {}),
        ("android_dismiss_alert", {}),
        ("android_terminate_app", {"app_id": "com.example.app"}),
        ("android_delete_session", {}),
    ]


@pytest.mark.asyncio
async def test_android_harness_retries_session_create() -> None:
    backend = _FakeAndroidBackend(failures=[("android_create_session", "Settings app is not running")])
    adapter = AndroidAppiumPlatformAdapter(
        HarnessPlatformSettings(type="android", automation="appium", session_create_retry_delay_seconds=0),
        backend=backend,
    )
    harness = AndroidHarness(adapter)

    await harness.run_setup()

    assert backend.calls[:2] == [
        ("android_create_session", {"platform": "android"}),
        ("android_create_session", {"platform": "android"}),
    ]


@pytest.mark.asyncio
async def test_android_harness_case_setup_requires_app_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capabilities_path = tmp_path / "capabilities.json"
    capabilities_path.write_text(json.dumps({"android": {"appium:udid": "device-1"}}), encoding="utf-8")
    monkeypatch.setenv("CAPABILITIES_CONFIG", str(capabilities_path))
    backend = _FakeAndroidBackend()
    adapter = AndroidAppiumPlatformAdapter(HarnessPlatformSettings(type="android", automation="appium"), backend=backend)
    harness = AndroidHarness(adapter)

    await harness.run_setup()

    with pytest.raises(ToolExecutionError, match="appium:appPackage"):
        await harness.case_setup(Task(description="Run case."))


def test_android_platform_adapter_does_not_fallback_to_hardcoded_capabilities_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fallback_path = tmp_path / ".fsq-agent-workspace" / "appium-capabilities.local.json"
    fallback_path.parent.mkdir()
    fallback_path.write_text(json.dumps({"android": {"appium:appPackage": "com.example.app"}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CAPABILITIES_CONFIG", raising=False)
    adapter = AndroidAppiumPlatformAdapter(HarnessPlatformSettings(type="android", automation="appium"), backend=_FakeAndroidBackend())

    assert adapter.app_id() is None


@pytest.mark.asyncio
async def test_harness_invoke_action_emits_platform_events() -> None:
    events: list[RunEvent] = []
    backend = _FakeAndroidBackend()
    adapter = AndroidAppiumPlatformAdapter(HarnessPlatformSettings(type="android", automation="appium"), backend=backend)
    harness = AndroidHarness(adapter, event_sink=events.append, run_id="run-1", task_id="task-1")

    await harness.invoke_action("android_tap", {"target": "Login"})

    assert [event.type for event in events] == ["platform_action_started", "platform_action_completed"]
    assert events[0].payload["action_name"] == "android_tap"
    assert events[1].payload["status"] == "success"


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
