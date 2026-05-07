import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from auto_test_agent.models import ShellSettings, SkillBundle, ToolExecutionError
from auto_test_agent.tools._cli_runner import CLIRunner
from auto_test_agent.tools._file_ops import FileOps
from auto_test_agent.tools._shell_executor import ShellCommandExecutor


class _CLIArgs(BaseModel):
    tool_name: str = Field(description="Configured CLI tool name to execute.")
    arguments: list[str] = Field(default_factory=list, description="Arguments appended to the configured command.")


class _ReadFileArgs(BaseModel):
    path: str = Field(description="Workspace-relative path to read.")


class _WriteFileArgs(BaseModel):
    path: str = Field(description="Workspace-relative path to write.")
    content: str = Field(description="Text content to write.")


class AgentsToolFactory:
    def __init__(self, cli_runner: CLIRunner, file_ops: FileOps, shell_settings: ShellSettings | None = None) -> None:
        self.cli_runner = cli_runner
        self.file_ops = file_ops
        self.shell_settings = shell_settings or ShellSettings()

    def build_tools(self, skills: list[SkillBundle] | None = None) -> list[Any]:
        try:
            from agents import FunctionTool, ShellTool
        except ImportError as exc:
            raise ToolExecutionError("openai-agents is required when OpenAI Agents SDK is enabled.") from exc

        tools: list[Any] = []
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
        result = await self.cli_runner.run(parsed.tool_name, {"args": parsed.arguments})
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    async def _read_file(self, _ctx: Any, args: str) -> str:
        parsed = _ReadFileArgs.model_validate_json(args)
        result = await self.file_ops.read_text({"path": parsed.path})
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    async def _write_file(self, _ctx: Any, args: str) -> str:
        parsed = _WriteFileArgs.model_validate_json(args)
        result = await self.file_ops.write_text({"path": parsed.path, "content": parsed.content})
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)