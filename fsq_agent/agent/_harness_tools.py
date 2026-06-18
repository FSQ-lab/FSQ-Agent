import itertools
import json
import time
from typing import Any

from fsq_agent.core import HarnessInterface
from fsq_agent.models import (
    ANDROID_ACTION_DEFINITIONS_BY_NAME,
    ConfigurationError,
    EvidencePolicy,
    ExecutableStep,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    HarnessFunctionSchema,
    StepPhase,
)


class HarnessToolAdapter:
    def __init__(
        self,
        harness: HarnessInterface,
        *,
        reserved_tool_names: set[str] | None = None,
        default_evidence_policy: EvidencePolicy | None = None,
    ) -> None:
        self.harness = harness
        self.reserved_tool_names = reserved_tool_names or set()
        self.default_evidence_policy = default_evidence_policy or EvidencePolicy()
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
                    evidence_policy=self.default_evidence_policy.model_copy(deep=True),
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
                artifact_refs: list[HarnessArtifactRef] = []
                artifact_errors: list[str] = []
                before_refs, before_errors = self._capture_artifacts(
                    step=step,
                    context=context,
                    phase="prepare",
                    reason="before-action",
                    enabled=step.evidence_policy.capture_before,
                )
                artifact_refs.extend(before_refs)
                artifact_errors.extend(before_errors)
                try:
                    result = self.harness.invoke_action(step, context)
                except Exception as exc:
                    failure_refs, failure_errors = self._capture_artifacts(
                        step=step,
                        context=context,
                        phase="finalize",
                        reason="failure",
                        enabled=step.evidence_policy.capture_on_failure,
                    )
                    artifact_refs.extend(failure_refs)
                    artifact_errors.extend(failure_errors)
                    return self._format_failure(schema, exc, int((time.perf_counter() - started) * 1000), artifact_refs, artifact_errors)
                after_refs, after_errors = self._capture_artifacts(
                    step=step,
                    context=context,
                    phase="finalize",
                    reason="after-action",
                    enabled=step.evidence_policy.capture_after,
                )
                artifact_refs.extend(after_refs)
                artifact_errors.extend(after_errors)
                if result.status in {"failed", "cancelled", "skipped"}:
                    failure_refs, failure_errors = self._capture_artifacts(
                        step=step,
                        context=context,
                        phase="finalize",
                        reason="failure",
                        enabled=step.evidence_policy.capture_on_failure,
                    )
                    artifact_refs.extend(failure_refs)
                    artifact_errors.extend(failure_errors)
                return self._format_success(schema, result, int((time.perf_counter() - started) * 1000), artifact_refs, artifact_errors)
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

    def _capture_artifacts(
        self,
        *,
        step: ExecutableStep,
        context: HarnessContext,
        phase: StepPhase,
        reason: str,
        enabled: bool,
    ) -> tuple[list[HarnessArtifactRef], list[str]]:
        if not enabled or not step.evidence_policy.artifact_kinds:
            return [], []
        refs: list[HarnessArtifactRef] = []
        errors: list[str] = []
        for kind in step.evidence_policy.artifact_kinds:
            try:
                refs.append(
                    self.harness.capture_artifact(
                        kind=kind,
                        reason=reason,
                        context=context,
                        step_id=step.step_id,
                        phase=phase,
                    )
                )
            except Exception as exc:
                errors.append(str(exc) or exc.__class__.__name__)
        return refs, errors

    def _format_success(
        self,
        schema: HarnessFunctionSchema,
        result: HarnessActionResult,
        duration_ms: int,
        artifact_refs: list[HarnessArtifactRef] | None = None,
        artifact_errors: list[str] | None = None,
    ) -> str:
        merged_result = result.model_copy(update={"artifact_refs": [*result.artifact_refs, *(artifact_refs or [])]})
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
            "result": merged_result.model_dump(mode="json"),
            "evidence_artifact_refs": [ref.model_dump(mode="json") for ref in artifact_refs or []],
            "evidence_artifact_errors": artifact_errors or [],
            "metadata": schema.metadata,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _format_failure(
        self,
        schema: HarnessFunctionSchema,
        error: Exception,
        duration_ms: int,
        artifact_refs: list[HarnessArtifactRef] | None = None,
        artifact_errors: list[str] | None = None,
    ) -> str:
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
                "result": {
                    "status": "failed",
                    "action_name": schema.fsq_action_name or schema.driver_method,
                    "artifact_refs": [ref.model_dump(mode="json") for ref in artifact_refs or []],
                    "error_message": str(error) or error.__class__.__name__,
                    "failure_category": "harness_error",
                },
                "evidence_artifact_refs": [ref.model_dump(mode="json") for ref in artifact_refs or []],
                "evidence_artifact_errors": artifact_errors or [],
                "metadata": schema.metadata,
            },
            ensure_ascii=False,
            default=str,
        )