import itertools
import json
import time
from typing import Any

from fsq_agent.core import HarnessInterface
from fsq_agent.models import ANDROID_ACTION_DEFINITIONS_BY_NAME, ConfigurationError, ExecutableStep, HarnessActionResult, HarnessFunctionSchema


class HarnessToolAdapter:
    def __init__(
        self,
        harness: HarnessInterface,
        *,
        reserved_tool_names: set[str] | None = None,
    ) -> None:
        self.harness = harness
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
                    metadata={
                        "tool_origin": "harness",
                        "tool_name": schema.name,
                        "platform": schema.platform,
                        "driver_method": schema.driver_method,
                        "fsq_action_name": schema.fsq_action_name,
                        "schema_metadata": schema.metadata,
                    },
                )
                context = self.harness.get_context()
                result = self.harness.invoke_action(step, context)
                return self._format_success(schema, result, int((time.perf_counter() - started) * 1000))
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

    def _format_success(self, schema: HarnessFunctionSchema, result: HarnessActionResult, duration_ms: int) -> str:
        payload = {
            "tool_name": schema.name,
            "tool_origin": "harness",
            "platform": schema.platform,
            "driver_method": schema.driver_method,
            "fsq_action_name": schema.fsq_action_name,
            "status": result.status,
            "failure_category": result.failure_category,
            "error_message": result.error_message,
            "duration_ms": result.duration_ms or duration_ms,
            "result": result.model_dump(mode="json"),
            "metadata": schema.metadata,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _format_failure(self, schema: HarnessFunctionSchema, error: Exception, duration_ms: int) -> str:
        return json.dumps(
            {
                "tool_name": schema.name,
                "tool_origin": "harness",
                "platform": schema.platform,
                "driver_method": schema.driver_method,
                "fsq_action_name": schema.fsq_action_name,
                "status": "failed",
                "failure_category": "harness_error",
                "error_message": str(error) or error.__class__.__name__,
                "duration_ms": duration_ms,
                "metadata": schema.metadata,
            },
            ensure_ascii=False,
            default=str,
        )