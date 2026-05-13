import json
import os
import time
import inspect
from contextlib import AsyncExitStack
from typing import Any

from fsq_agent.config import Settings, validate_runtime_settings
from fsq_agent.models import AgentFinalOutput, ConfigurationError, KnowledgeBundle, RunEvent, RunEventSink, SkillBundle, StepResult, Task
from fsq_agent.tools import AgentsMCPFactory, AgentsToolFactory, LifecycleControllerFactory, MCPToolCaller
from fsq_agent.tools._tool_artifacts import ToolArtifactStore

from fsq_agent.agent._prompt import PromptModelBuilder, PromptRenderer
from fsq_agent.agent._structured_output import coerce_agent_final_output, coerce_string_list, serialize_agent_final_output


_LOCAL_TOOL_NAMES = {
    "publish_progress",
    "run_cli_tool",
    "read_file",
    "write_file",
    "search_artifact",
    "read_artifact_slice",
}


class _RecentToolOutputInputFilter:
    def __init__(
        self,
        sdk_filter: Any | None,
        recent_tool_outputs: int,
        max_output_chars: int,
        preview_chars: int,
        trimmable_tools: set[str] | None,
        artifact_store: ToolArtifactStore | None,
    ) -> None:
        self.sdk_filter = sdk_filter
        self.recent_tool_outputs = recent_tool_outputs
        self.max_output_chars = max_output_chars
        self.preview_chars = preview_chars
        self.trimmable_tools = trimmable_tools
        self.artifact_store = artifact_store
        self.artifact_paths_by_call_id: dict[str, str] = {}

    def __call__(self, data: Any) -> Any:
        from agents.run_config import ModelInputData

        model_data = self.sdk_filter(data) if self.sdk_filter else data.model_data
        items = model_data.input
        if not items or self.recent_tool_outputs < 0:
            return model_data

        call_id_to_names = self._call_id_to_names(items)
        output_indices = [index for index, item in enumerate(items) if isinstance(item, dict) and item.get("type") == "function_call_output"]
        protected = set(output_indices[-self.recent_tool_outputs :]) if self.recent_tool_outputs else set()
        new_items: list[Any] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict) or item.get("type") != "function_call_output":
                new_items.append(item)
                continue
            tool_names = call_id_to_names.get(str(item.get("call_id") or item.get("id") or ""), set())
            output = item.get("output", "")
            output_text = output if isinstance(output, str) else str(output)
            artifact_path = self._artifact_path_for(item, tool_names, output_text)
            if index in protected:
                new_items.append(item)
                continue
            if self.trimmable_tools and not tool_names.intersection(self.trimmable_tools):
                new_items.append(item)
                continue
            if len(output_text) <= self.max_output_chars:
                new_items.append(item)
                continue
            trimmed_item = dict(item)
            preview = output_text[: self.preview_chars]
            display_name = next(iter(tool_names), "tool")
            artifact_line = f" Artifact path: {artifact_path}." if artifact_path else ""
            trimmed_item["output"] = f"[Trimmed historical {display_name} output: {len(output_text)} chars, preview follows].{artifact_line}\n{preview}..."
            new_items.append(trimmed_item)
        return ModelInputData(input=new_items, instructions=model_data.instructions)

    def _call_id_to_names(self, items: list[Any]) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}
        for item in items:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            call_id = str(item.get("call_id") or item.get("id") or "")
            if not call_id:
                continue
            names = {str(value) for value in (item.get("name"), item.get("tool_name")) if value}
            mapping[call_id] = names
        return mapping

    def _artifact_path_for(self, item: dict[str, Any], tool_names: set[str], output_text: str) -> str | None:
        if not self.artifact_store:
            return None
        call_id = str(item.get("call_id") or item.get("id") or "")
        if call_id in self.artifact_paths_by_call_id:
            return self.artifact_paths_by_call_id[call_id]
        tool_name = next(iter(tool_names), "sdk_tool")
        path = self.artifact_store.write(tool_name, output_text, {"source": "model_input_filter", "call_id": call_id})
        if not path:
            return None
        artifact_path = str(path)
        if call_id:
            self.artifact_paths_by_call_id[call_id] = artifact_path
        return artifact_path


class OpenAIAgentsRuntime:
    def __init__(
        self,
        settings: Settings,
        tool_factory: AgentsToolFactory,
        mcp_factory: AgentsMCPFactory,
    ) -> None:
        self.settings = settings
        self.tool_factory = tool_factory
        self.mcp_factory = mcp_factory

    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[SkillBundle],
        run_id: str,
        event_sink: RunEventSink | None = None,
    ) -> list[StepResult]:
        validate_runtime_settings(self.settings)
        started = time.perf_counter()
        try:
            from agents import Agent, OpenAIProvider, RunConfig, Runner, set_tracing_disabled
            from agents.extensions import ToolOutputTrimmer
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ConfigurationError("openai-agents and openai packages are required when SDK runtime is enabled.") from exc

        set_tracing_disabled(not self.settings.openai_agents.tracing_enabled)
        client = AsyncOpenAI(
            api_key=os.environ[self.settings.openai_agents.api_key_env],
            base_url=self.settings.openai_agents.base_url,
        )
        provider = OpenAIProvider(openai_client=client, use_responses=self.settings.openai_agents.use_responses)
        try:
            try:
                async with AsyncExitStack() as stack:
                    mcp_servers, hosted_tools = await self.mcp_factory.enter_servers(stack)
                    lifecycle_controller = LifecycleControllerFactory.create(self.settings.lifecycle)
                    lifecycle_caller = MCPToolCaller(mcp_servers, run_id, task.id, event_sink)
                    lifecycle_setup_completed = False
                    validation_steps = self._build_mcp_validation_steps()
                    for step in validation_steps:
                        await self._emit(
                            event_sink,
                            RunEvent(
                                run_id=run_id,
                                task_id=task.id,
                                type="mcp_tools_listed",
                                title="MCP tool validation",
                                message=step.actual_outcome,
                                tool_name=step.tool_name,
                                payload={"step_id": step.step_id, "tool_output": step.tool_output},
                            ),
                        )
                    try:
                        await lifecycle_controller.batch_setup(lifecycle_caller)
                        lifecycle_setup_completed = True
                        await lifecycle_controller.case_setup(lifecycle_caller, task)
                        agent = Agent(
                            name=self.settings.agent.name,
                            model=self.settings.openai_agents.model,
                            instructions=self._build_instructions(knowledge, skills),
                            tools=[*self.tool_factory.build_tools(skills, run_id=run_id, task_id=task.id, event_sink=event_sink), *hosted_tools],
                            mcp_servers=mcp_servers,
                            mcp_config=self._build_mcp_config(),
                            output_type=AgentFinalOutput,
                        )
                        await self._emit(
                            event_sink,
                            RunEvent(
                                run_id=run_id,
                                task_id=task.id,
                                type="planning_started",
                                title="Planning started",
                                message="The agent is deriving success criteria and preparing the first actions.",
                            ),
                        )
                        result = Runner.run_streamed(
                            agent,
                            input=self._build_task_input(task, lifecycle_controller.runtime_policy()),
                            max_turns=self.settings.openai_agents.max_turns,
                            run_config=self._build_run_config(RunConfig, ToolOutputTrimmer, provider, run_id),
                        )
                        async for event in result.stream_events():
                            run_event = self._map_stream_event(event, run_id, task.id)
                            if run_event:
                                await self._emit(event_sink, run_event)
                    finally:
                        if lifecycle_setup_completed:
                            await lifecycle_controller.case_teardown(lifecycle_caller, task)
                            await lifecycle_controller.batch_teardown(lifecycle_caller)
            except Exception as exc:
                duration_ms = int((time.perf_counter() - started) * 1000)
                await self._emit(
                    event_sink,
                    RunEvent(
                        run_id=run_id,
                        task_id=task.id,
                        type="run_failed",
                        title="SDK run failed",
                        message=str(exc),
                        duration_ms=duration_ms,
                    ),
                )
                return [
                    StepResult(
                        step_id=1,
                        status="failed",
                        actual_outcome="OpenAI Agents SDK run failed before producing structured verification output.",
                        duration_ms=duration_ms,
                        error=str(exc),
                        tool_name="openai_agents.runner",
                    )
                ]
        finally:
            await client.close()

        duration_ms = int((time.perf_counter() - started) * 1000)
        final_output = coerce_agent_final_output(result.final_output) or str(result.final_output)
        serialized_final_output = serialize_agent_final_output(final_output)
        pre_plan_steps = self._build_pre_plan_step_results(final_output, duration_ms)
        structured_steps = [
            *validation_steps,
            *self._offset_step_ids(pre_plan_steps, len(validation_steps)),
        ]
        return [
            *structured_steps,
            StepResult(
                step_id=len(structured_steps) + 1,
                status="success",
                actual_outcome=serialized_final_output,
                duration_ms=duration_ms,
                tool_name="openai_agents.runner",
                tool_output=final_output.model_dump(mode="json") if isinstance(final_output, AgentFinalOutput) else serialized_final_output,
            )
        ]

    async def _emit(self, event_sink: RunEventSink | None, event: RunEvent) -> None:
        if not event_sink:
            return
        result = event_sink(event)
        if inspect.isawaitable(result):
            await result

    def _build_run_config(self, run_config_cls: Any, tool_output_trimmer_cls: Any, provider: Any, run_id: str = "") -> Any:
        trimming = self.settings.openai_agents.context_trimming
        local_output = self.settings.openai_agents.local_tool_output
        input_filter = None
        if trimming.enabled:
            trimmable_tools = set(trimming.trimmable_tools) if trimming.trimmable_tools else None
            artifact_store = (
                ToolArtifactStore(self.settings.output.runs_dir, run_id, local_output)
                if run_id and local_output.artifact_enabled
                else None
            )
            sdk_filter = tool_output_trimmer_cls(
                recent_turns=trimming.recent_turns,
                max_output_chars=trimming.max_tool_output_chars,
                preview_chars=trimming.preview_chars,
                trimmable_tools=frozenset(trimmable_tools) if trimmable_tools else None,
            )
            input_filter = _RecentToolOutputInputFilter(
                sdk_filter,
                local_output.recent_full_output_count,
                trimming.max_tool_output_chars,
                trimming.preview_chars,
                trimmable_tools,
                artifact_store,
            )
        return run_config_cls(model_provider=provider, call_model_input_filter=input_filter)

    def _build_mcp_config(self) -> dict[str, Any]:
        return {"convert_schemas_to_strict": self.settings.mcp_tool_validation.strict_schema}

    def _map_stream_event(self, event: Any, run_id: str, task_id: str) -> RunEvent | None:
        event_type = getattr(event, "type", "")
        if event_type == "agent_updated_stream_event":
            new_agent = getattr(event, "new_agent", None)
            agent_name = getattr(new_agent, "name", "agent")
            return RunEvent(run_id=run_id, task_id=task_id, type="agent_started", title="Agent updated", message=str(agent_name))
        if event_type != "run_item_stream_event":
            return None

        name = getattr(event, "name", "")
        item = getattr(event, "item", None)
        if name == "tool_called":
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="tool_call_started",
                title="Tool call started",
                message=self._tool_call_message(item),
                tool_name=self._tool_name(item),
                tool_call_id=self._tool_call_id(item),
                tool_arguments=self._tool_arguments(item),
                payload={"tool_origin": self._tool_origin(self._tool_name(item))},
            )
        if name == "tool_output":
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="tool_call_completed",
                title="Tool call completed",
                message=self._tool_output_message(item),
                tool_call_id=self._tool_call_id(item),
                tool_output_preview=self._preview(getattr(item, "output", None)),
                payload={"artifact_path": self._artifact_path_from_output(getattr(item, "output", None))},
            )
        if name == "reasoning_item_created":
            summary = self._reasoning_summary(item)
            return RunEvent(run_id=run_id, task_id=task_id, type="reasoning_summary", title="Reasoning summary", message=summary)
        if name == "mcp_list_tools":
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="mcp_tools_listed",
                title="MCP tools listed",
                message=self._preview(getattr(item, "raw_item", item)),
            )
        if name == "message_output_created":
            return RunEvent(
                run_id=run_id,
                task_id=task_id,
                type="planning_update",
                title="Agent message",
                message=self._preview(getattr(item, "raw_item", item)),
            )
        return None

    def _tool_name(self, item: Any) -> str | None:
        value = getattr(item, "tool_name", None)
        if value:
            return str(value)
        raw_item = getattr(item, "raw_item", None)
        if isinstance(raw_item, dict):
            return raw_item.get("name")
        return str(getattr(raw_item, "name", "")) or None

    def _tool_call_id(self, item: Any) -> str | None:
        value = getattr(item, "call_id", None)
        if value:
            return str(value)
        raw_item = getattr(item, "raw_item", None)
        if isinstance(raw_item, dict):
            return str(raw_item.get("call_id") or raw_item.get("id") or "") or None
        return str(getattr(raw_item, "call_id", None) or getattr(raw_item, "id", "")) or None

    def _tool_arguments(self, item: Any) -> dict[str, Any] | str | None:
        raw_item = getattr(item, "raw_item", None)
        if isinstance(raw_item, dict):
            return self._redact(raw_item.get("arguments") or raw_item.get("input") or raw_item)
        arguments = getattr(raw_item, "arguments", None) or getattr(raw_item, "input", None)
        return self._redact(arguments) if arguments is not None else None

    def _tool_call_message(self, item: Any) -> str:
        tool_name = self._tool_name(item) or "tool"
        return f"Calling {tool_name}."

    def _tool_output_message(self, item: Any) -> str:
        return "Tool returned output."

    def _reasoning_summary(self, item: Any) -> str:
        raw_item = getattr(item, "raw_item", None)
        summary = getattr(raw_item, "summary", None)
        if isinstance(summary, list) and summary:
            return self._preview(summary)
        if isinstance(summary, str) and summary:
            return summary
        return "The model produced a reasoning summary."

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

    def _offset_step_ids(self, steps: list[StepResult], offset: int) -> list[StepResult]:
        if offset <= 0:
            return steps
        return [step.model_copy(update={"step_id": step.step_id + offset}) for step in steps]

    def _build_mcp_validation_steps(self) -> list[StepResult]:
        get_validation_issues = getattr(self.mcp_factory, "get_validation_issues", None)
        if not callable(get_validation_issues):
            return []
        issues = get_validation_issues()
        steps: list[StepResult] = []
        for index, issue in enumerate(issues, start=1):
            outcome = f"Ignored MCP tool `{issue.server_name}.{issue.tool_name}`: {issue.reason}"
            if issue.schema_path:
                outcome = f"{outcome} at {issue.schema_path}"
            steps.append(
                StepResult(
                    step_id=index,
                    status="skipped",
                    actual_outcome=outcome,
                    tool_name="mcp_tool_validation",
                    tool_output=issue.model_dump(mode="json"),
                )
            )
        return steps

    def _build_pre_plan_step_results(self, final_output: AgentFinalOutput | str, duration_ms: int) -> list[StepResult]:
        payload = coerce_agent_final_output(final_output)
        if not payload:
            return []
        pre_plan = payload.pre_plan
        plan_updates = payload.plan_updates
        steps: list[StepResult] = []
        for index, item in enumerate(pre_plan, start=1):
            steps.append(self._build_pre_plan_step(index, item.model_dump(mode="json"), plan_updates, duration_ms))
        return steps

    def _build_pre_plan_step(
        self,
        fallback_step_id: int,
        item: dict[str, Any],
        plan_updates: list[str],
        duration_ms: int,
    ) -> StepResult:
        raw_step_id = item.get("step_id", fallback_step_id)
        step_id = raw_step_id if isinstance(raw_step_id, int) and raw_step_id >= 1 else fallback_step_id
        raw_status = str(item.get("status", "skipped")).lower()
        status = raw_status if raw_status in {"success", "failed", "skipped", "adjusted"} else "skipped"
        action = str(item.get("action") or "Pre-plan step")
        success_criteria = coerce_string_list(item.get("success_criteria"))
        lines = [f"Action: {action}"]
        if success_criteria:
            lines.extend(["Success criteria:", *[f"- {criterion}" for criterion in success_criteria]])
        if status == "adjusted" and plan_updates:
            lines.extend(["Plan updates:", *[f"- {update}" for update in plan_updates]])
        return StepResult(
            step_id=step_id,
            status=status,
            actual_outcome="\n".join(lines),
            duration_ms=duration_ms,
            tool_name="pre_plan",
            tool_output=item,
        )

    def _build_instructions(self, knowledge: KnowledgeBundle, skills: list[SkillBundle]) -> str:
        prompt = self.settings.openai_agents.prompt
        model = PromptModelBuilder(prompt).build_agent_prompt(knowledge, skills)
        return PromptRenderer(prompt).render_agent_prompt(model)

    def _build_task_input(self, task: Task, runtime_policy: list[str] | None = None) -> str:
        prompt = self.settings.openai_agents.prompt
        model = PromptModelBuilder(prompt).build_task_prompt(task, runtime_policy)
        return PromptRenderer(prompt).render_task_prompt(model)

    def _tool_origin(self, tool_name: str | None) -> str:
        if not tool_name:
            return "unknown"
        if tool_name == "shell":
            return "shell"
        if tool_name in _LOCAL_TOOL_NAMES:
            return "local"
        return "mcp"

    def _artifact_path_from_output(self, output: Any) -> str | None:
        if isinstance(output, str):
            text = output
        else:
            text = str(output) if output is not None else ""
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        artifact = payload.get("artifact")
        if isinstance(artifact, dict) and artifact.get("path"):
            return str(artifact["path"])
        return None
