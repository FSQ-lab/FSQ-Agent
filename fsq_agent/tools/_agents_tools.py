import json
import inspect
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fsq_agent.models import RunEvent, RunEventSink, ShellSettings, SkillBundle, ToolExecutionError
from fsq_agent.tools._cli_runner import CLIRunner
from fsq_agent.tools._file_ops import FileOps
from fsq_agent.tools._shell_executor import ShellCommandExecutor


class _CLIArgs(BaseModel):
    tool_name: str = Field(description="Configured CLI tool name to execute.")
    arguments: list[str] = Field(default_factory=list, description="Arguments appended to the configured command.")


class _ReadFileArgs(BaseModel):
    path: str = Field(description="Workspace-relative path to read.")


class _WriteFileArgs(BaseModel):
    path: str = Field(description="Workspace-relative path to write.")
    content: str = Field(description="Text content to write.")


class _ProgressArgs(BaseModel):
    kind: str = Field(default="planning_update", description="Progress kind: planning, planning_update, or reasoning.")
    message: str = Field(description="Short user-visible progress summary. Do not include hidden chain-of-thought.")
    next_action: str | None = Field(default=None, description="Optional next action summary.")


class AgentsToolFactory:
    def __init__(self, cli_runner: CLIRunner, file_ops: FileOps, shell_settings: ShellSettings | None = None) -> None:
        self.cli_runner = cli_runner
        self.file_ops = file_ops
        self.shell_settings = shell_settings or ShellSettings()
        self.run_id = ""
        self.task_id = ""
        self.event_sink: RunEventSink | None = None

    def build_tools(
        self,
        skills: list[SkillBundle] | None = None,
        *,
        run_id: str = "",
        task_id: str = "",
        event_sink: RunEventSink | None = None,
    ) -> list[Any]:
        try:
            from agents import FunctionTool, ShellTool
        except ImportError as exc:
            raise ToolExecutionError("openai-agents is required when OpenAI Agents SDK is enabled.") from exc

        self.run_id = run_id
        self.task_id = task_id
        self.event_sink = event_sink
        tools: list[Any] = []
        tools.append(
            FunctionTool(
                name="publish_progress",
                description="Publish a short user-visible planning or reasoning summary. Do not include hidden chain-of-thought.",
                params_json_schema=_ProgressArgs.model_json_schema(),
                on_invoke_tool=self._publish_progress,
            )
        )
        if self.cli_runner.list_tools():
            tools.append(
                FunctionTool(
                    name="run_cli_tool",
                    description="Run one configured allowlisted CLI tool.",
                    params_json_schema=_CLIArgs.model_json_schema(),
                    on_invoke_tool=self._run_cli_tool,
                )
            )
        tools.extend(
            [
                FunctionTool(
                    name="read_file",
                    description="Read a scoped workspace file.",
                    params_json_schema=_ReadFileArgs.model_json_schema(),
                    on_invoke_tool=self._read_file,
                ),
                FunctionTool(
                    name="write_file",
                    description="Write a scoped workspace file.",
                    params_json_schema=_WriteFileArgs.model_json_schema(),
                    on_invoke_tool=self._write_file,
                ),
            ]
        )
        if self.shell_settings.enabled:
            tools.append(
                ShellTool(
                    executor=ShellCommandExecutor(self.shell_settings).execute,
                    environment={"type": "local", "skills": self._build_local_shell_skills(skills or [])},
                )
            )
        return tools

    def _build_local_shell_skills(self, skills: list[SkillBundle]) -> list[dict[str, str]]:
        shell_skills: list[dict[str, str]] = []
        for skill in skills:
            path = self._skill_path(skill)
            if path is None:
                continue
            shell_skills.append(
                {
                    "name": skill.name,
                    "description": skill.description or f"Instructions for using CLI capabilities for {skill.name}.",
                    "path": str(path),
                }
            )
        return shell_skills

    def _skill_path(self, skill: SkillBundle) -> Path | None:
        if not skill.files:
            return None
        if len(skill.files) == 1:
            return skill.files[0]
        parents = {file.parent for file in skill.files}
        return parents.pop() if len(parents) == 1 else skill.files[0].parent

    async def _run_cli_tool(self, _ctx: Any, args: str) -> str:
        parsed = _CLIArgs.model_validate_json(args)
        started = time.perf_counter()
        await self._emit_tool_started("run_cli_tool", parsed.model_dump(mode="json"))
        try:
            result = await self.cli_runner.run(parsed.tool_name, {"args": parsed.arguments})
        except Exception as exc:
            await self._emit_tool_failed("run_cli_tool", str(exc), started)
            raise
        output = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        await self._emit_tool_completed("run_cli_tool", output, started)
        return output

    async def _read_file(self, _ctx: Any, args: str) -> str:
        parsed = _ReadFileArgs.model_validate_json(args)
        started = time.perf_counter()
        await self._emit_tool_started("read_file", parsed.model_dump(mode="json"))
        try:
            result = await self.file_ops.read_text({"path": parsed.path})
        except Exception as exc:
            await self._emit_tool_failed("read_file", str(exc), started)
            raise
        output = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        await self._emit_tool_completed("read_file", output, started)
        return output

    async def _write_file(self, _ctx: Any, args: str) -> str:
        parsed = _WriteFileArgs.model_validate_json(args)
        started = time.perf_counter()
        await self._emit_tool_started("write_file", {"path": parsed.path, "content": "<redacted>"})
        try:
            result = await self.file_ops.write_text({"path": parsed.path, "content": parsed.content})
        except Exception as exc:
            await self._emit_tool_failed("write_file", str(exc), started)
            raise
        output = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
        await self._emit_tool_completed("write_file", output, started)
        return output

    async def _publish_progress(self, _ctx: Any, args: str) -> str:
        parsed = _ProgressArgs.model_validate_json(args)
        event_type = "reasoning_summary" if parsed.kind == "reasoning" else "planning_update"
        title = "Reasoning summary" if event_type == "reasoning_summary" else "Planning update"
        message = parsed.message if not parsed.next_action else f"{parsed.message} Next: {parsed.next_action}"
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type=event_type,
                title=title,
                message=message,
                payload={"kind": parsed.kind, "next_action": parsed.next_action},
            )
        )
        return json.dumps({"ok": True}, ensure_ascii=False)

    async def _emit_tool_started(self, tool_name: str, arguments: dict[str, Any] | str) -> None:
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_started",
                title="Tool call started",
                message=f"Calling {tool_name}.",
                tool_name=tool_name,
                tool_arguments=self._redact(arguments),
            )
        )

    async def _emit_tool_completed(self, tool_name: str, output: str, started: float) -> None:
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_completed",
                title="Tool call completed",
                message=f"{tool_name} completed.",
                tool_name=tool_name,
                tool_output_preview=self._preview(output),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )

    async def _emit_tool_failed(self, tool_name: str, error: str, started: float) -> None:
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_failed",
                title="Tool call failed",
                message=error,
                tool_name=tool_name,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
        )

    async def _emit(self, event: RunEvent) -> None:
        if not self.event_sink or not self.run_id or not self.task_id:
            return
        result = self.event_sink(event)
        if inspect.isawaitable(result):
            await result

    def _preview(self, value: Any, limit: int = 1000) -> str:
        text = value if isinstance(value, str) else repr(value)
        text = text.replace("\r", " ").replace("\n", " ")
        return text if len(text) <= limit else f"{text[:limit]}..."

    def _redact(self, value: Any) -> Any:
        sensitive = ("token", "key", "secret", "password", "authorization", "cookie")
        if isinstance(value, dict):
            return {key: "***" if any(part in str(key).lower() for part in sensitive) else self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value
