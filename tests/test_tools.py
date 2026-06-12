from pathlib import Path

import json

import pytest

from fsq_agent.models import (
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
    AgentsToolFactory,
    CLIRunner,
    CapabilityRegistry,
    FileOps,
    ToolExecutor,
)


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
async def test_direct_harness_execution_is_runtime_owned(tmp_path: Path) -> None:
    registry = CapabilityRegistry.from_cli_tools([])
    registry.register(ToolDefinition(name="tap_on", kind="harness"))
    executor = ToolExecutor(registry, CLIRunner([]), FileOps(tmp_path))

    with pytest.raises(ToolExecutionError, match="Unsupported tool kind"):
        await executor.execute(ToolCall(tool_name="tap_on", arguments={}))


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



