import itertools
import json
import time
from typing import Any

from fsq_agent.core import HarnessInterface, StepRunner
from fsq_agent.models import ANDROID_ACTION_DEFINITIONS_BY_NAME, ConfigurationError, EvidencePolicy, ExecutableStep, HarnessFunctionSchema, RunnerStepResult


_UI_MUTATING_ACTIONS = {
    "launchApp",
    "killApp",
    "tapOn",
    "performActions",
    "pressKey",
    "inputText",
    "longPressOn",
    "swipe",
}


class HarnessToolAdapter:
    def __init__(
        self,
        harness: HarnessInterface,
        *,
        run_id: str,
        reserved_tool_names: set[str] | None = None,
    ) -> None:
        self.harness = harness
        self.run_id = run_id
        self.runner = StepRunner(harness=harness)
        self.reserved_tool_names = reserved_tool_names or set()
        self._counter = itertools.count(1)
        self.schemas = self._discover_schemas()
        self.schemas_by_name = {schema.name: schema for schema in self.schemas}

    @property
    def tool_names(self) -> set[str]:
        return set(self.schemas_by_name)

    def build_tools(self, function_tool_cls: Any) -> list[Any]:
        return [
            function_tool_cls(
                name=schema.name,
                description=schema.description or f"Run platform action {schema.name} through the active harness.",
                params_json_schema=schema.params_json_schema,
                on_invoke_tool=self._handler_for(schema),
            )
            for schema in self.schemas
        ]

    def _discover_schemas(self) -> list[HarnessFunctionSchema]:
        try:
            schemas = self.harness.action_space()
        except Exception as exc:
            raise ConfigurationError("Harness action-space discovery failed.", context={"error": str(exc)}) from exc
        names: set[str] = set()
        for schema in schemas:
            if schema.name in names:
                raise ConfigurationError("Harness action-space contains duplicate tool names.", context={"tool_name": schema.name})
            if schema.name in self.reserved_tool_names:
                raise ConfigurationError("Harness action-space conflicts with a local tool name.", context={"tool_name": schema.name})
            names.add(schema.name)
        return schemas

    def _handler_for(self, schema: HarnessFunctionSchema):
        async def invoke(_ctx: Any, args: str) -> str:
            started = time.perf_counter()
            try:
                params = self._parse_args(args)
                action_name = schema.fsq_action_name or schema.driver_method
                step = ExecutableStep(
                    step_id=f"agent-{schema.name}-{next(self._counter)}",
                    kind=self._step_kind(action_name),
                    action_name=action_name,
                    params=params,
                    evidence_policy=self._evidence_policy(action_name),
                    metadata={
                        "run_id": self.run_id,
                        "tool_origin": "harness",
                        "tool_name": schema.name,
                        "platform": schema.platform,
                        "driver_method": schema.driver_method,
                        "fsq_action_name": schema.fsq_action_name,
                        "schema_metadata": schema.metadata,
                    },
                )
                result = self.runner.run_step(run_id=self.run_id, step=step)
                return self._format_runner_result(schema, step, result, int((time.perf_counter() - started) * 1000))
            except Exception as exc:
                return self._format_failure(schema, exc, int((time.perf_counter() - started) * 1000))

        return invoke

    def _parse_args(self, args: str) -> dict[str, Any]:
        if not args:
            return {}
        payload = json.loads(args)
        if not isinstance(payload, dict):
            raise ValueError("Harness tool arguments must be a JSON object.")
        return payload

    def _step_kind(self, action_name: str):
        action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(action_name)
        if action_definition is not None:
            return action_definition.step_kind
        return "action"

    def _evidence_policy(self, action_name: str) -> EvidencePolicy:
        if action_name in _UI_MUTATING_ACTIONS:
            return EvidencePolicy(
                capture_before=True,
                capture_after=True,
                capture_on_failure=True,
                artifact_kinds=["screenshot", "ui_tree"],
            )
        return EvidencePolicy()

    def _format_runner_result(
        self,
        schema: HarnessFunctionSchema,
        step: ExecutableStep,
        runner_result: RunnerStepResult,
        duration_ms: int,
    ) -> str:
        artifact_refs = self._artifact_refs(runner_result)
        result_summary = self._result_summary(schema, step, runner_result, artifact_refs)
        payload = {
            "tool_name": schema.name,
            "tool_origin": "harness",
            "platform": schema.platform,
            "driver_method": schema.driver_method,
            "fsq_action_name": schema.fsq_action_name,
            "status": runner_result.status,
            "failure_category": runner_result.failure_category,
            "error_message": runner_result.error_message,
            "duration_ms": runner_result.duration_ms or duration_ms,
            "result": result_summary,
            "metadata": schema.metadata,
            "runner_step_id": runner_result.step_id,
            "runner_result": runner_result.model_dump(mode="json"),
            "artifact_refs": artifact_refs,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _result_summary(
        self,
        schema: HarnessFunctionSchema,
        step: ExecutableStep,
        runner_result: RunnerStepResult,
        artifact_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        invoke_metadata = self._invoke_metadata(runner_result)
        metadata: dict[str, Any] = {
            "tool_origin": "harness",
            "tool_name": schema.name,
            "platform": schema.platform,
            "driver_method": schema.driver_method,
            "fsq_action_name": schema.fsq_action_name,
            "schema_metadata": schema.metadata,
        }
        harness_metadata = invoke_metadata.get("harness_metadata")
        if isinstance(harness_metadata, dict):
            metadata["harness_metadata"] = harness_metadata
        return {
            "status": runner_result.status,
            "action_name": step.action_name,
            "duration_ms": runner_result.duration_ms,
            "output": invoke_metadata.get("harness_output"),
            "artifact_refs": artifact_refs,
            "error_message": runner_result.error_message,
            "failure_category": runner_result.failure_category,
            "metadata": metadata,
        }

    def _invoke_metadata(self, runner_result: RunnerStepResult) -> dict[str, Any]:
        for phase_report in runner_result.phase_reports:
            if phase_report.phase == "invoke":
                return dict(phase_report.metadata)
        return {}

    def _artifact_refs(self, runner_result: RunnerStepResult) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for phase_report in runner_result.phase_reports:
            refs.extend(ref.model_dump(mode="json") for ref in phase_report.artifact_refs)
        return refs

    def _format_failure(self, schema: HarnessFunctionSchema, error: Exception, duration_ms: int) -> str:
        error_message = str(error) or error.__class__.__name__
        action_name = schema.fsq_action_name or schema.driver_method
        return json.dumps(
            {
                "tool_name": schema.name,
                "tool_origin": "harness",
                "platform": schema.platform,
                "driver_method": schema.driver_method,
                "fsq_action_name": schema.fsq_action_name,
                "status": "failed",
                "failure_category": "harness_error",
                "error_message": error_message,
                "duration_ms": duration_ms,
                "result": {
                    "status": "failed",
                    "action_name": action_name,
                    "artifact_refs": [],
                    "error_message": error_message,
                    "failure_category": "harness_error",
                    "metadata": {
                        "tool_origin": "harness",
                        "tool_name": schema.name,
                        "platform": schema.platform,
                        "driver_method": schema.driver_method,
                        "fsq_action_name": schema.fsq_action_name,
                        "schema_metadata": schema.metadata,
                    },
                },
                "metadata": schema.metadata,
                "artifact_refs": [],
            },
            ensure_ascii=False,
            default=str,
        )
