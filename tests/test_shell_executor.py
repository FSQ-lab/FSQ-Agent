from types import SimpleNamespace

import pytest

from fsq_agent.models import ShellSettings, ToolExecutionError
from fsq_agent.tools import ShellCommandExecutor


def _request(*commands: str, timeout_ms: int | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        data=SimpleNamespace(
            action=SimpleNamespace(commands=list(commands), timeout_ms=timeout_ms),
        )
    )


@pytest.mark.asyncio
async def test_shell_executor_blocks_commands_outside_allowlist(tmp_path) -> None:
    executor = ShellCommandExecutor(
        ShellSettings(enabled=True, mode="allowlist", command_allowlist=["echo"], working_dir=tmp_path)
    )

    with pytest.raises(ToolExecutionError, match="allowlist"):
        await executor.execute(_request("python --version"))


@pytest.mark.asyncio
async def test_shell_executor_runs_allowlisted_command(tmp_path) -> None:
    executor = ShellCommandExecutor(
        ShellSettings(enabled=True, mode="allowlist", command_allowlist=["echo"], working_dir=tmp_path)
    )

    output = await executor.execute(_request("echo hello"))

    assert "exit_code: 0" in output
    assert "hello" in output


@pytest.mark.asyncio
async def test_shell_executor_allow_all_runs_unlisted_command(tmp_path) -> None:
    executor = ShellCommandExecutor(
        ShellSettings(enabled=True, mode="allow_all", command_allowlist=[], working_dir=tmp_path)
    )

    output = await executor.execute(_request("echo free"))

    assert "exit_code: 0" in output
    assert "free" in output