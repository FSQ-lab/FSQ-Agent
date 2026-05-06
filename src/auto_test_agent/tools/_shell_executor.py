import asyncio
import shlex
import time
from pathlib import Path
from typing import Any

from auto_test_agent.models import ShellSettings, ToolExecutionError


class ShellCommandExecutor:
    def __init__(self, settings: ShellSettings) -> None:
        self.settings = settings
        self._allowed_commands = {command.lower() for command in settings.command_allowlist}

    async def execute(self, request: Any) -> str:
        commands = list(getattr(request.data.action, "commands", []))
        timeout_seconds = self._timeout_seconds(getattr(request.data.action, "timeout_ms", None))
        outputs = []
        for command in commands:
            command_text = str(command)
            self._validate_command(command_text)
            outputs.append(await self._run_command(command_text, timeout_seconds))
        return "\n".join(outputs)

    def _timeout_seconds(self, timeout_ms: int | None) -> int:
        if timeout_ms is None:
            return self.settings.timeout_seconds
        return max(1, min(self.settings.timeout_seconds, int(timeout_ms / 1000)))

    def _validate_command(self, command: str) -> None:
        if self.settings.mode == "allow_all":
            return
        command_name = self._command_name(command)
        if command_name.lower() not in self._allowed_commands:
            raise ToolExecutionError(
                "Shell command is not in the configured allowlist.",
                context={"command": command_name, "allowlist": self.settings.command_allowlist},
            )

    def _command_name(self, command: str) -> str:
        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            raise ToolExecutionError("Unable to parse shell command.", context={"command": command}) from exc
        if not parts:
            raise ToolExecutionError("Shell command cannot be empty.")
        token = parts[0].strip('"\'')
        return Path(token).name or token

    async def _run_command(self, command: str, timeout_seconds: int) -> str:
        started = time.perf_counter()
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.settings.working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            return f"$ {command}\nstatus: timeout after {timeout_seconds}s"
        duration_ms = int((time.perf_counter() - started) * 1000)
        stdout_text = stdout.decode(errors="replace").strip()
        stderr_text = stderr.decode(errors="replace").strip()
        lines = [f"$ {command}", f"exit_code: {process.returncode}", f"duration_ms: {duration_ms}"]
        if stdout_text:
            lines.extend(["stdout:", stdout_text])
        if stderr_text:
            lines.extend(["stderr:", stderr_text])
        return "\n".join(lines)