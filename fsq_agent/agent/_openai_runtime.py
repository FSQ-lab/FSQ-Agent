import os
import time
import inspect
from contextlib import AsyncExitStack
from typing import Any

from fsq_agent.config import Settings, validate_runtime_settings
from fsq_agent.models import ConfigurationError, KnowledgeBundle, RunEvent, RunEventSink, SkillBundle, StepResult, Task
from fsq_agent.tools import AgentsMCPFactory, AgentsToolFactory

from fsq_agent.agent._structured_output import coerce_string_list, parse_structured_output


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
                    agent = Agent(
                        name=self.settings.agent.name,
                        model=self.settings.openai_agents.model,
                        instructions=self._build_instructions(knowledge, skills),
                        tools=[*self.tool_factory.build_tools(skills, run_id=run_id, task_id=task.id, event_sink=event_sink), *hosted_tools],
                        mcp_servers=mcp_servers,
                        mcp_config={"convert_schemas_to_strict": True},
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
                        input=self._build_task_input(task),
                        max_turns=self.settings.openai_agents.max_turns,
                        run_config=RunConfig(model_provider=provider),
                    )
                    async for event in result.stream_events():
                        run_event = self._map_stream_event(event, run_id, task.id)
                        if run_event:
                            await self._emit(event_sink, run_event)
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
        final_output = str(result.final_output)
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
                actual_outcome=final_output,
                duration_ms=duration_ms,
                tool_name="openai_agents.runner",
                tool_output=final_output,
            )
        ]

    async def _emit(self, event_sink: RunEventSink | None, event: RunEvent) -> None:
        if not event_sink:
            return
        result = event_sink(event)
        if inspect.isawaitable(result):
            await result

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

    def _build_pre_plan_step_results(self, final_output: str, duration_ms: int) -> list[StepResult]:
        payload = parse_structured_output(final_output)
        if not payload:
            return []
        pre_plan = payload.get("pre_plan")
        if not isinstance(pre_plan, list):
            return []
        plan_updates = coerce_string_list(payload.get("plan_updates"))
        steps: list[StepResult] = []
        for index, item in enumerate(pre_plan, start=1):
            if not isinstance(item, dict):
                continue
            steps.append(self._build_pre_plan_step(index, item, plan_updates, duration_ms))
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
        lines = [
            "You are fsq-agent, a non-interactive goal-driven testing agent.",
            "Your job is to complete exactly one user-provided automation task by using configured MCP servers, local tools, and loaded skills.",
            "The user normally provides only a task description. Treat user-provided acceptance criteria as optional extra constraints, not required input.",
            "Before taking external actions, derive the acceptance criteria from the task description, private knowledge, matched flow templates, and loaded skills.",
            "If the task description is too broad or underspecified to derive domain-specific checks, define success as completing the executable task flow without unrecovered errors and with enough evidence to show the flow finished.",
            "First create a pre-plan before taking external actions. The pre-plan must include the derived or user-provided acceptance criteria that define success.",
            "Use the publish_progress tool to report short user-visible planning updates, reasoning summaries, and plan changes before major external actions. Do not include hidden chain-of-thought; summarize only what is safe and useful for the user to see.",
            "Execute the pre-plan step by step with available MCP/tool/skill capabilities.",
            "Dynamically adjust the pre-plan when tool results, MCP capabilities, page state, application state, or skill instructions show a better route is needed.",
            "Use private knowledge and flow templates as planning context when they are provided.",
            "When the task description contains FSQ AI Test DSL case context, treat its command flow as an advisory reference, not as a brittle script. Prefer its locators and assertions, but adapt for live UI state, transient dialogs, optional setup, missing steps, and recovery needs.",
            "Do not modify source FSQ YAML case files during execution.",
            "Do not ask the user for clarification during a run. Finish with success evidence, failure evidence, or a clear inconclusive summary.",
            "Use only configured tools for external actions. Respect scoped file and CLI tool boundaries.",
            "The final answer must be JSON only, with no Markdown fences and no prose outside JSON.",
            "The final JSON schema is:",
            '{"status":"success|failed|inconclusive","summary":"string","pre_plan":[{"step_id":1,"action":"string","success_criteria":["string"],"status":"success|failed|skipped|adjusted"}],"plan_updates":["string"],"satisfied_criteria":["string"],"unmet_criteria":["string"],"evidence":["string"],"errors":["string"]}',
            "Use satisfied_criteria and unmet_criteria to report the concrete criteria you derived or received from the user.",
            "Use status=success only when every derived or user-provided task acceptance criterion is satisfied with evidence.",
            "Use status=failed when one or more criteria cannot be satisfied or an execution step fails permanently.",
            "Use status=inconclusive when the task ran but available evidence cannot prove success or failure.",
        ]
        if knowledge.items:
            lines.extend(["", "Private knowledge:"])
            lines.extend(f"- {key}: {value}" for key, value in knowledge.items.items())
        if knowledge.flow_templates:
            lines.extend(["", "Relevant flow templates:"])
            lines.extend(f"- {name}: {template}" for name, template in knowledge.flow_templates.items())
        if knowledge.warnings:
            lines.extend(["", "Knowledge warnings:"])
            lines.extend(f"- {warning}" for warning in knowledge.warnings)
        for skill in skills:
            if skill.instructions:
                lines.extend(["", f"Skill: {skill.name}", skill.instructions])
            lines.extend(f"Skill warning: {warning}" for warning in skill.warnings)
        return "\n".join(lines)

    def _build_task_input(self, task: Task) -> str:
        lines = [
            f"Task ID: {task.id}\n"
            f"Task Name: {task.name}\n"
            f"Description:\n{task.description}\n\n"
        ]
        if task.acceptance_criteria:
            criteria = "\n".join(f"- {criterion}" for criterion in task.acceptance_criteria)
            lines.append(f"User-provided acceptance criteria:\n{criteria}\n")
        else:
            lines.append(
                "User-provided acceptance criteria: none. Derive acceptance criteria from the description, "
                "knowledge, and matched flows. If the description is too broad, use successful flow completion "
                "as the success standard.\n"
            )
        return "".join(lines)