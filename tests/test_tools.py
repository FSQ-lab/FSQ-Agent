from pathlib import Path

import json

import pytest

from fsq_agent.models import CommonToolCall, LocalToolOutputSettings, RunEvent, RuntimeSecretSettings, ToolExecutionError
from fsq_agent.tools import AgentsCommonToolAdapter, CommonToolExecutor, CommonToolRegistry, DefaultCommonToolProvider, FileOps


class _FakeFunctionTool:
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.description = kwargs["description"]
        self.params_json_schema = kwargs["params_json_schema"]
        self.on_invoke_tool = kwargs["on_invoke_tool"]


def _provider(tmp_path: Path, **kwargs) -> DefaultCommonToolProvider:
    return DefaultCommonToolProvider(FileOps(tmp_path), **kwargs)


def _registry(provider: DefaultCommonToolProvider) -> CommonToolRegistry:
    return CommonToolRegistry.from_providers([provider])


@pytest.mark.asyncio
async def test_common_tool_file_ops_are_scoped(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    executor = CommonToolExecutor(_registry(provider))

    result = await executor.execute(
        CommonToolCall(tool_name="write_file", arguments={"path": "nested/out.txt", "content": "hello"})
    )

    assert result.status == "success"
    assert (tmp_path / "nested" / "out.txt").read_text(encoding="utf-8") == "hello"


def test_common_tool_registry_lists_only_common_capabilities(tmp_path: Path) -> None:
    names = {definition.name for definition in _registry(_provider(tmp_path)).list_tools()}

    assert names == {
        "read_file",
        "write_file",
        "get_runtime_secret",
        "search_artifact",
        "read_artifact_slice",
        "wait_ms",
    }
    assert "run_cli_tool" not in names
    assert "submit_visual_assertion" not in names
    assert "publish_progress" not in names
    assert "shell" not in names


@pytest.mark.asyncio
async def test_direct_harness_execution_is_not_common_tool_owned(tmp_path: Path) -> None:
    executor = CommonToolExecutor(_registry(_provider(tmp_path)))

    with pytest.raises(ToolExecutionError, match="Unknown CommonTool"):
        await executor.execute(CommonToolCall(tool_name="tap_on", arguments={}))


@pytest.mark.asyncio
async def test_agents_common_tool_adapter_wait_ms_returns_pure_wait_result(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    adapter = AgentsCommonToolAdapter(_registry(provider))
    tools = adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1")

    wait_tool = next(tool for tool in tools if tool.name == "wait_ms")
    output = await wait_tool.on_invoke_tool(None, json.dumps({"duration_ms": 1, "reason": "page-load pause"}))

    payload = json.loads(output)
    assert payload["result"]["output"]["type"] == "wait_completed"
    assert payload["result"]["output"]["duration_ms"] == 1
    assert payload["result"]["output"]["elapsed_ms"] >= 0
    assert payload["result"]["output"]["reason"] == "page-load pause"


@pytest.mark.asyncio
async def test_agents_common_tool_adapter_runtime_secret_is_allowlisted_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "secret-password")
    events: list[RunEvent] = []
    provider = _provider(
        tmp_path,
        runtime_secret_settings=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
    )
    adapter = AgentsCommonToolAdapter(_registry(provider))
    secret_tool = next(
        tool for tool in adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1", event_sink=events.append)
        if tool.name == "get_runtime_secret"
    )

    output = await secret_tool.on_invoke_tool(None, json.dumps({"name": "TEST_ACCOUNT_PASSWORD"}))

    payload = json.loads(output)
    assert payload["result"]["output"]["value"] == "secret-password"
    assert payload["result"]["sensitive"] is True
    assert "secret-password" not in events[-1].tool_output_preview
    assert '"value": "***"' in events[-1].tool_output_preview


@pytest.mark.asyncio
async def test_agents_common_tool_adapter_runtime_secret_never_uses_preview_branch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_value = "s" * 2000
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", secret_value)
    events: list[RunEvent] = []
    provider = _provider(
        tmp_path,
        runtime_secret_settings=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
    )
    settings = LocalToolOutputSettings(full_output_max_chars=10, model_response_max_chars=500)
    adapter = AgentsCommonToolAdapter(_registry(provider), local_tool_output_settings=settings)
    secret_tool = next(
        tool for tool in adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1", event_sink=events.append)
        if tool.name == "get_runtime_secret"
    )

    output = await secret_tool.on_invoke_tool(None, json.dumps({"name": "TEST_ACCOUNT_PASSWORD"}))

    payload = json.loads(output)
    assert payload["model_output"] == "full"
    assert payload["sensitive"] is True
    assert "preview" not in payload
    assert payload["result"]["output"]["value"] == secret_value
    assert secret_value not in events[-1].tool_output_preview
    assert '"value": "***"' in events[-1].tool_output_preview


@pytest.mark.asyncio
async def test_common_tool_runtime_secret_rejects_unlisted_name(tmp_path: Path) -> None:
    executor = CommonToolExecutor(_registry(_provider(tmp_path)))

    with pytest.raises(ToolExecutionError, match="not allowed"):
        await executor.execute(CommonToolCall(tool_name="get_runtime_secret", arguments={"name": "TEST_ACCOUNT_PASSWORD"}))


@pytest.mark.asyncio
async def test_common_tool_writes_full_output_artifact_and_returns_inline(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    provider = _provider(
        tmp_path,
        local_tool_output_settings=LocalToolOutputSettings(full_output_max_chars=1000),
        runs_dir=runs_dir,
        run_id="run-1",
    )
    adapter = AgentsCommonToolAdapter(_registry(provider), local_tool_output_settings=LocalToolOutputSettings(full_output_max_chars=1000))
    read_target = tmp_path / "file.txt"
    read_target.write_text("hello", encoding="utf-8")
    read_tool = next(tool for tool in adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1") if tool.name == "read_file")

    output = await read_tool.on_invoke_tool(None, json.dumps({"path": "file.txt"}))

    payload = json.loads(output)
    artifact_path = Path(payload["artifact"]["path"])
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["model_output"] == "full"
    assert payload["result"]["output"]["output"] == "hello"
    assert artifact["metadata"] == {"path": "file.txt"}
    assert '"output": "hello"' in artifact["content"]


@pytest.mark.asyncio
async def test_common_tool_large_output_uses_artifact_search_and_slice(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    settings = LocalToolOutputSettings(
        full_output_max_chars=1000,
        historical_preview_chars=20,
        model_response_max_chars=500,
    )
    provider = _provider(tmp_path, local_tool_output_settings=settings, runs_dir=runs_dir, run_id="run-1")
    adapter = AgentsCommonToolAdapter(_registry(provider), local_tool_output_settings=settings)
    (tmp_path / "large.txt").write_text("alpha beta gamma " * 100, encoding="utf-8")
    tools = adapter.build_tools(_FakeFunctionTool, run_id="run-1", task_id="task-1")
    read_tool = next(tool for tool in tools if tool.name == "read_file")
    search_tool = next(tool for tool in tools if tool.name == "search_artifact")
    slice_tool = next(tool for tool in tools if tool.name == "read_artifact_slice")

    output = await read_tool.on_invoke_tool(None, json.dumps({"path": "large.txt"}))
    payload = json.loads(output)

    assert payload["model_output"] == "artifact_reference"
    assert "result" not in payload
    search_output = await search_tool.on_invoke_tool(
        None,
        json.dumps({"artifact_path": payload["artifact"]["path"], "query": "gamma", "max_matches": 1, "context_chars": 20}),
    )
    search_payload = json.loads(search_output)
    assert search_payload["result"]["output"]["matches"][0]["offset"] >= 0

    slice_output = await slice_tool.on_invoke_tool(
        None,
        json.dumps(
            {
                "artifact_path": payload["artifact"]["path"],
                "offset": search_payload["result"]["output"]["matches"][0]["offset"],
                "length": 30,
            }
        ),
    )
    assert "gamma" in json.loads(slice_output)["result"]["output"]["content"]
