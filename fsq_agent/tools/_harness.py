from abc import ABC
from typing import Any

from fsq_agent.models import HarnessSettings, PlatformActionDefinition, PlatformActionResult, RunEvent, RunEventSink, Task, ToolExecutionError
from fsq_agent.tools._platform import PlatformAdapter


class Harness(ABC):
    def __init__(
        self,
        adapter: PlatformAdapter | None = None,
        event_sink: RunEventSink | None = None,
        run_id: str = "",
        task_id: str = "",
    ) -> None:
        self.adapter = adapter
        self.event_sink = event_sink
        self.run_id = run_id
        self.task_id = task_id

    def action_space(self, consumer: str = "agent") -> list[PlatformActionDefinition]:
        if self.adapter is None:
            return []
        definitions = self.adapter.action_space()
        if consumer == "agent":
            return [definition for definition in definitions if definition.visibility == "agent_visible"]
        if consumer == "runner":
            return [definition for definition in definitions if definition.visibility in {"agent_visible", "runner_only"}]
        if consumer == "lifecycle":
            return [definition for definition in definitions if definition.visibility == "lifecycle_only"]
        return definitions

    async def invoke_action(
        self,
        action_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> PlatformActionResult:
        if self.adapter is None or self.adapter.action_definition(action_name) is None:
            result = PlatformActionResult(
                action_name=action_name,
                status="failed",
                error=f"Unsupported platform action: {action_name}",
                failure_category="unsupported_action",
            )
            await self._emit_platform_action("platform_action_failed", result, params)
            return result
        action_call = {"action_name": action_name, "params": params}
        await self._emit_platform_action(
            "platform_action_started",
            PlatformActionResult(action_name=action_name, status="skipped"),
            params,
        )
        await self.before_action(action_call, context)
        result = await self.adapter.invoke_action(action_name, params, context)
        await self.after_action(action_call, result, context)
        await self._emit_platform_action(
            "platform_action_failed" if result.status == "failed" else "platform_action_completed",
            result,
            params,
        )
        return result

    async def run_setup(self, context: dict[str, Any] | None = None) -> None:
        return None

    async def run_teardown(self, context: dict[str, Any] | None = None) -> None:
        return None

    async def case_setup(self, task: Task, context: dict[str, Any] | None = None) -> None:
        return None

    async def case_teardown(self, task: Task, context: dict[str, Any] | None = None) -> None:
        return None

    async def before_action(self, action_call: dict[str, Any], context: dict[str, Any] | None = None) -> None:
        return None

    async def after_action(
        self,
        action_call: dict[str, Any],
        result: PlatformActionResult,
        context: dict[str, Any] | None = None,
    ) -> None:
        return None

    def runtime_policy(self) -> list[str]:
        return []

    async def _emit_platform_action(
        self,
        event_type: str,
        result: PlatformActionResult,
        params: dict[str, Any],
    ) -> None:
        title_action = result.action_name or "platform action"
        await emit_harness_event(
            self.event_sink,
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type=event_type,
                title="Platform action started" if event_type == "platform_action_started" else "Platform action completed" if event_type == "platform_action_completed" else "Platform action failed",
                message=f"Running platform action {title_action}." if event_type == "platform_action_started" else result.error or f"Platform action {title_action} completed.",
                duration_ms=result.duration_ms,
                payload={
                    "action_name": result.action_name,
                    "action_arguments": params,
                    "status": result.status,
                    "failure_category": result.failure_category,
                    "evidence_refs": result.evidence_refs,
                    "backend_debug_preview": result.backend_debug,
                },
            ),
        )


class NoopHarness(Harness):
    def __init__(self) -> None:
        super().__init__(None)


class HarnessFactory:
    _ALIASES: dict[str, type[Harness]] = {
        "": NoopHarness,
        "none": NoopHarness,
        "noop": NoopHarness,
        "NoopHarness": NoopHarness,
    }

    @classmethod
    def create(
        cls,
        settings: HarnessSettings,
        event_sink: RunEventSink | None = None,
        run_id: str = "",
        task_id: str = "",
        platform_backend: Any = None,
    ) -> Harness:
        if settings.name in {"android", "AndroidHarness"}:
            from fsq_agent.tools._android_harness import AndroidHarness, AndroidAppiumPlatformAdapter

            return AndroidHarness(
                AndroidAppiumPlatformAdapter(settings.platform, backend=platform_backend),
                options=settings.options,
                event_sink=event_sink,
                run_id=run_id,
                task_id=task_id,
            )
        harness_cls = cls._ALIASES.get(settings.name)
        if harness_cls is None:
            raise ToolExecutionError(
                "Unknown harness.",
                context={"harness": settings.name, "available": sorted([*cls._ALIASES, "android", "AndroidHarness"])},
            )
        return harness_cls()


async def emit_harness_event(event_sink: RunEventSink | None, event: RunEvent) -> None:
    if not event_sink:
        return
    result = event_sink(event)
    if hasattr(result, "__await__"):
        await result
