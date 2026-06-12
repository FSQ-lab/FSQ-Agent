import asyncio
import json
import inspect
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from fsq_agent.models import LocalToolOutputSettings, RunEvent, RunEventSink, RuntimeSecretSettings, ShellSettings, SkillBundle, ToolExecutionError
from fsq_agent.tools._cli_runner import CLIRunner
from fsq_agent.tools._file_ops import FileOps
from fsq_agent.tools._shell_executor import ShellCommandExecutor
from fsq_agent.tools._tool_artifacts import ToolArtifactStore


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


class _SubmitVisualAssertionArgs(BaseModel):
    assertion_id: str = Field(description="Stable identifier or ordered key action label for this visual assertion.")
    prompt: str = Field(description="Natural-language visual assertion prompt to evaluate against the screenshot.")
    screenshot_path: str = Field(description="Fresh screenshot path produced by a screenshot tool for this assertion.")


class _WaitArgs(BaseModel):
    duration_ms: int = Field(ge=1, le=60000, description="Pure wait duration in milliseconds. Use this for FSQ pause actions instead of gestures.")
    reason: str | None = Field(default=None, description="Optional short reason for the wait.")


class _RuntimeSecretArgs(BaseModel):
    name: str = Field(description="Allowed environment variable name to retrieve for the current run.")


class _SearchArtifactArgs(BaseModel):
    artifact_path: str = Field(description="Artifact path returned by a previous tool response.")
    query: str = Field(description="Text to search for inside the artifact.")
    case_sensitive: bool = Field(default=False, description="Whether the search is case-sensitive.")
    max_matches: int = Field(default=20, ge=1, le=100, description="Maximum number of matches to return.")
    context_chars: int = Field(default=300, ge=0, le=2000, description="Characters of context around each match.")


class _ReadArtifactSliceArgs(BaseModel):
    artifact_path: str = Field(description="Artifact path returned by a previous tool response.")
    offset: int = Field(default=0, ge=0, description="Character offset to start reading from.")
    length: int = Field(default=12000, ge=1, le=30000, description="Maximum characters to read.")


class AgentsToolFactory:
    def __init__(
        self,
        cli_runner: CLIRunner,
        file_ops: FileOps,
        shell_settings: ShellSettings | None = None,
        local_tool_output_settings: LocalToolOutputSettings | None = None,
        runs_dir: Path | None = None,
        runtime_secret_settings: RuntimeSecretSettings | None = None,
    ) -> None:
        self.cli_runner = cli_runner
        self.file_ops = file_ops
        self.shell_settings = shell_settings or ShellSettings()
        self.local_tool_output_settings = local_tool_output_settings or LocalToolOutputSettings()
        self.runs_dir = runs_dir
        self.runtime_secret_settings = runtime_secret_settings or RuntimeSecretSettings()
        self.run_id = ""
        self.task_id = ""
        self.event_sink: RunEventSink | None = None
        self.artifact_store: ToolArtifactStore | None = None

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
            raise ToolExecutionError("openai-agents is required when the OpenAI Agents SDK runtime is used.") from exc

        self.run_id = run_id
        self.task_id = task_id
        self.event_sink = event_sink
        self.artifact_store = (
            ToolArtifactStore(self.runs_dir, run_id, self.local_tool_output_settings)
            if self.runs_dir and run_id and self.local_tool_output_settings.artifact_enabled
            else None
        )
        tools: list[Any] = []
        tools.append(
            FunctionTool(
                name="publish_progress",
                description="Publish a short user-visible planning or reasoning summary. Do not include hidden chain-of-thought.",
                params_json_schema=_ProgressArgs.model_json_schema(),
                on_invoke_tool=self._publish_progress,
            )
        )
        tools.append(
            FunctionTool(
                name="submit_visual_assertion",
                description=(
                    "Bind a fresh screenshot path to a visual assertion prompt, such as FSQ assertWithAI. "
                    "Call this after taking the screenshot and before marking the visual assertion satisfied."
                ),
                params_json_schema=_SubmitVisualAssertionArgs.model_json_schema(),
                on_invoke_tool=self._submit_visual_assertion,
            )
        )
        tools.append(
            FunctionTool(
                name="wait_ms",
                description=(
                    "Wait without touching or changing the UI. Use this for FSQ performActions pause steps "
                    "and page-load delays instead of platform gestures such as scroll or long_press."
                ),
                params_json_schema=_WaitArgs.model_json_schema(),
                on_invoke_tool=self._wait_ms,
            )
        )
        if self.runtime_secret_settings.allowed_env_names:
            tools.append(
                FunctionTool(
                    name="get_runtime_secret",
                    description=(
                        "Retrieve one configured runtime secret from environment or .env-loaded values. "
                        "Use only for required setup such as sign-in. Never echo secret values in progress, evidence, or final output. "
                        f"Allowed names: {', '.join(self.runtime_secret_settings.allowed_env_names)}."
                    ),
                    params_json_schema=_RuntimeSecretArgs.model_json_schema(),
                    on_invoke_tool=self._get_runtime_secret,
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
                FunctionTool(
                    name="search_artifact",
                    description="Search a large tool-output artifact by text and return offsets with local context.",
                    params_json_schema=_SearchArtifactArgs.model_json_schema(),
                    on_invoke_tool=self._search_artifact,
                ),
                FunctionTool(
                    name="read_artifact_slice",
                    description="Read a bounded character slice from a large tool-output artifact by offset and length.",
                    params_json_schema=_ReadArtifactSliceArgs.model_json_schema(),
                    on_invoke_tool=self._read_artifact_slice,
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
        output = self._format_tool_response(
            "run_cli_tool",
            result.model_dump(mode="json"),
            {"configured_tool": parsed.tool_name},
        )
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
        output = self._format_tool_response("read_file", result.model_dump(mode="json"), {"path": parsed.path})
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
        output = self._format_tool_response("write_file", result.model_dump(mode="json"), {"path": parsed.path})
        await self._emit_tool_completed("write_file", output, started)
        return output

    async def _search_artifact(self, _ctx: Any, args: str) -> str:
        parsed = _SearchArtifactArgs.model_validate_json(args)
        started = time.perf_counter()
        await self._emit_tool_started("search_artifact", parsed.model_dump(mode="json"))
        try:
            if not self.artifact_store:
                raise ToolExecutionError("Tool artifact storage is not enabled for this run.")
            result = self.artifact_store.search(
                parsed.artifact_path,
                parsed.query,
                parsed.case_sensitive,
                parsed.max_matches,
                parsed.context_chars,
            )
        except Exception as exc:
            await self._emit_tool_failed("search_artifact", str(exc), started)
            raise
        output = json.dumps(result, ensure_ascii=False)
        await self._emit_tool_completed("search_artifact", output, started)
        return output

    async def _read_artifact_slice(self, _ctx: Any, args: str) -> str:
        parsed = _ReadArtifactSliceArgs.model_validate_json(args)
        started = time.perf_counter()
        await self._emit_tool_started("read_artifact_slice", parsed.model_dump(mode="json"))
        try:
            if not self.artifact_store:
                raise ToolExecutionError("Tool artifact storage is not enabled for this run.")
            result = self.artifact_store.read_slice(parsed.artifact_path, parsed.offset, parsed.length)
        except Exception as exc:
            await self._emit_tool_failed("read_artifact_slice", str(exc), started)
            raise
        output = json.dumps(result, ensure_ascii=False)
        await self._emit_tool_completed("read_artifact_slice", output, started)
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

    async def _submit_visual_assertion(self, _ctx: Any, args: str) -> str:
        parsed = _SubmitVisualAssertionArgs.model_validate_json(args)
        return json.dumps(
            {
                "type": "visual_assertion_submission",
                "assertion_id": parsed.assertion_id,
                "prompt": parsed.prompt,
                "screenshot_path": parsed.screenshot_path,
                "next_step": "Inspect the attached screenshot image in the next model turn before deciding this visual assertion.",
            },
            ensure_ascii=False,
        )

    async def _wait_ms(self, _ctx: Any, args: str) -> str:
        parsed = _WaitArgs.model_validate_json(args)
        started = time.perf_counter()
        await asyncio.sleep(parsed.duration_ms / 1000)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        output = json.dumps(
            {
                "type": "wait_completed",
                "duration_ms": parsed.duration_ms,
                "elapsed_ms": elapsed_ms,
                "reason": parsed.reason,
            },
            ensure_ascii=False,
        )
        return output

    async def _get_runtime_secret(self, _ctx: Any, args: str) -> str:
        parsed = _RuntimeSecretArgs.model_validate_json(args)
        started = time.perf_counter()
        await self._emit_tool_started("get_runtime_secret", {"name": parsed.name})
        if parsed.name not in set(self.runtime_secret_settings.allowed_env_names):
            await self._emit_tool_failed("get_runtime_secret", "Runtime secret name is not allowed.", started)
            raise ToolExecutionError("Runtime secret name is not allowed.", context={"name": parsed.name})
        value = os.getenv(parsed.name)
        if not value:
            await self._emit_tool_failed("get_runtime_secret", "Runtime secret is not set.", started)
            raise ToolExecutionError("Runtime secret is not set.", context={"name": parsed.name})
        output = json.dumps(
            {"type": "runtime_secret", "name": parsed.name, "value": value, "sensitive": True},
            ensure_ascii=False,
        )
        await self._emit_tool_completed("get_runtime_secret", self._redact_sensitive_tool_output(output), started)
        return output

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
                payload={"tool_origin": "local"},
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
                payload={"tool_origin": "local", "artifact_path": self._artifact_path_from_response(output)},
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
                payload={"tool_origin": "local"},
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
        text = self._redact_sensitive_tool_output(text)
        text = text.replace("\r", " ").replace("\n", " ")
        return text if len(text) <= limit else f"{text[:limit]}..."

    def _redact_sensitive_tool_output(self, text: str) -> str:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(payload, dict) and payload.get("sensitive") is True:
            redacted = dict(payload)
            if "value" in redacted:
                redacted["value"] = "***"
            return json.dumps(redacted, ensure_ascii=False)
        return text

    def _format_tool_response(self, tool_name: str, payload: dict[str, Any], metadata: dict[str, Any]) -> str:
        full_output = json.dumps(payload, ensure_ascii=False)
        artifact_path = self.artifact_store.write(tool_name, full_output, metadata) if self.artifact_store else None
        settings = self.local_tool_output_settings
        artifact = {
            "path": str(artifact_path) if artifact_path else None,
            "content_chars": len(full_output),
        }
        if len(full_output) <= settings.full_output_max_chars:
            return json.dumps(
                {
                    "tool_name": tool_name,
                    "model_output": "full",
                    "artifact": artifact,
                    "result": payload,
                },
                ensure_ascii=False,
            )

        preview = full_output[: settings.historical_preview_chars]
        response = {
            "tool_name": tool_name,
            "model_output": settings.historical_output_mode,
            "artifact": artifact,
            "preview": preview,
            "instructions": "Use search_artifact or read_artifact_slice with artifact.path when details beyond the preview are needed.",
        }
        encoded = json.dumps(response, ensure_ascii=False)
        if len(encoded) <= settings.model_response_max_chars:
            return encoded
        preview_limit = len(preview)
        while preview_limit > 0:
            response["preview"] = preview[:preview_limit]
            encoded = json.dumps(response, ensure_ascii=False)
            if len(encoded) <= settings.model_response_max_chars:
                return encoded
            preview_limit //= 2
        response["preview"] = ""
        return json.dumps(response, ensure_ascii=False)

    def _artifact_path_from_response(self, output: str) -> str | None:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        artifact = payload.get("artifact")
        if isinstance(artifact, dict) and artifact.get("path"):
            return str(artifact["path"])
        return None

    def _redact(self, value: Any) -> Any:
        sensitive = ("token", "key", "secret", "password", "authorization", "cookie")
        if isinstance(value, dict):
            return {key: "***" if any(part in str(key).lower() for part in sensitive) else self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value
