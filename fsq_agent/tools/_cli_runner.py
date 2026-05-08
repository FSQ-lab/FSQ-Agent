import asyncio
import time
from collections.abc import Mapping
from pathlib import Path

from fsq_agent.models import CLIToolConfig, ToolExecutionError, ToolResult


class CLIRunner:
    def __init__(self, cli_tools: list[CLIToolConfig], cwd: Path | None = None) -> None:
        self._tools = {tool.name: tool for tool in cli_tools}
        self.cwd = cwd

    def list_tools(self) -> list[CLIToolConfig]:
        return list(self._tools.values())

    async def run(
        self,
        name: str,
        arguments: Mapping[str, object] | None = None,
        *,
        timeout_seconds: int | None = None,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolExecutionError("Unknown CLI tool.", context={"tool": name})

        arguments = arguments or {}
        extra_args = arguments.get("args", [])
        if isinstance(extra_args, str):
            extra_args = [extra_args]
        if not isinstance(extra_args, list) or not all(isinstance(arg, str) for arg in extra_args):
            raise ToolExecutionError("CLI tool arguments must be a string list.", context={"tool": name})

        command = [tool.command, *tool.args, *extra_args]
        timeout = timeout_seconds or tool.timeout_seconds
        started = time.perf_counter()
        process: asyncio.subprocess.Process | None = None
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.cwd) if self.cwd is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            if process and process.returncode is None:
                process.kill()
                await process.wait()
            duration_ms = int((time.perf_counter() - started) * 1000)
            return ToolResult(tool_name=name, status="failed", error="Command timed out.", duration_ms=duration_ms)
        except OSError as exc:
            raise ToolExecutionError("Unable to start CLI tool.", context={"tool": name, "command": command}) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        output = stdout.decode(errors="replace").strip()
        error = stderr.decode(errors="replace").strip() or None
        status = "success" if process.returncode == 0 else "failed"
        return ToolResult(
            tool_name=name,
            status=status,
            output=output,
            error=error,
            duration_ms=duration_ms,
            raw={"returncode": process.returncode, "command": command},
        )