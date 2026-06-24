import time
from collections.abc import Sequence
from dataclasses import dataclass, field

from fsq_agent.core._capabilities import CapabilityExecutorBindings, CapabilityRegistry
from fsq_agent.core.harness import HarnessInterface
from fsq_agent.models import (
    CapabilityDefinition,
    CapabilityExecutionResult,
    EvidenceArtifactRef,
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    RunnerEvent,
    RunnerEventType,
    RunnerStatus,
    RunnerStepResult,
    StepPhase,
    StepPhaseReport,
)


@dataclass
class _StepExecutionState:
    started: float = field(default_factory=time.perf_counter)
    phase_reports: list[StepPhaseReport] = field(default_factory=list)
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    artifact_error_message: str | None = None


class StepRunner:
    def __init__(
        self,
        harness: HarnessInterface,
        *,
        capability_registry: CapabilityRegistry | None = None,
        executor_bindings: CapabilityExecutorBindings | None = None,
    ) -> None:
        self.harness = harness
        self.capability_registry = capability_registry or CapabilityRegistry()
        self.executor_bindings = executor_bindings or CapabilityExecutorBindings()
        self._events: list[RunnerEvent] = []
        self._last_capability_execution_result: CapabilityExecutionResult | None = None

    @property
    def events(self) -> Sequence[RunnerEvent]:
        return tuple(self._events)

    @property
    def last_capability_execution_result(self) -> CapabilityExecutionResult | None:
        return self._last_capability_execution_result

    def run_step(self, run_id: str, step: ExecutableStep) -> RunnerStepResult:
        self._events = []
        self._last_capability_execution_result = None
        capability, step = self._resolve_capability_step(step)
        state = self._start_step(run_id, step)
        if capability is not None and capability.executor_kind == "common":
            return self._run_common_step(run_id, step, capability, state)

        return self._run_harness_step(run_id, step, state)

    def _resolve_capability_step(self, step: ExecutableStep) -> tuple[CapabilityDefinition | None, ExecutableStep]:
        capability = self.capability_registry.resolve(step.action_name)
        if capability is not None and capability.name != step.action_name:
            return capability, step.model_copy(update={"action_name": capability.name})
        return capability, step

    def _start_step(self, run_id: str, step: ExecutableStep) -> _StepExecutionState:
        state = _StepExecutionState()
        self._emit(run_id=run_id, event_type="step_start", step=step)
        return state

    def _run_harness_step(self, run_id: str, step: ExecutableStep, state: _StepExecutionState) -> RunnerStepResult:
        context = self._run_harness_prepare_phase(run_id, step, state)
        action_result = self._run_harness_invoke_phase(run_id, step, state, context)
        self._run_harness_finalize_phase(run_id, step, state, context, action_result)
        status = self._result_status(action_result, state.failure_category, state.artifact_error_message)
        return self._finish_step(
            run_id,
            step,
            state,
            status=status,
            failure_category="artifact_error" if state.artifact_error_message else state.failure_category,
            error_message=state.artifact_error_message or state.error_message,
        )

    def _run_harness_prepare_phase(self, run_id: str, step: ExecutableStep, state: _StepExecutionState) -> object:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="prepare")
        context = self.harness.get_context()
        prepare_artifacts, prepare_error = self._capture_artifacts(
            run_id=run_id,
            step=step,
            context=context,
            phase="prepare",
            reason="before-action",
            enabled=step.evidence_policy.capture_before,
        )
        if prepare_error:
            state.artifact_error_message = prepare_error
        self.harness.before_action(step, context)
        self._append_phase_report(
            state,
            step=step,
            phase="prepare",
            status="failed" if prepare_error else "passed",
            failure_category="artifact_error" if prepare_error else None,
            error_message=prepare_error,
            artifact_refs=prepare_artifacts,
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="prepare")
        return context

    def _run_harness_invoke_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        context: object,
    ) -> HarnessActionResult | None:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="invoke")
        self._emit(run_id=run_id, event_type="harness_call_start", step=step, phase="invoke")
        action_result: HarnessActionResult | None = None
        try:
            action_result = self.harness.invoke_action(step, context)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            if action_result.status in {"failed", "cancelled", "skipped"}:
                state.failure_category = action_result.failure_category
                state.error_message = action_result.error_message
                self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            self._append_phase_report(
                state,
                step=step,
                phase="invoke",
                status=action_result.status,
                artifact_refs=self._action_result_artifacts(run_id, step, action_result, "invoke"),
                metadata=self._action_result_metadata(action_result),
            )
        except Exception as exc:  # noqa: BLE001 - runner converts phase exceptions into structured results.
            state.failure_category = self.harness.classify_error(exc, "invoke", step)
            state.error_message = str(exc)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            self._append_phase_report(
                state,
                step=step,
                phase="invoke",
                status="failed",
                failure_category=state.failure_category,
                error_message=state.error_message,
            )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="invoke")
        return action_result

    def _run_harness_finalize_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        context: object,
        action_result: HarnessActionResult | None,
    ) -> None:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="finalize")
        self.harness.after_action(step, context, action_result)
        finalize_artifacts: list[EvidenceArtifactRef] = []
        finalize_errors: list[str] = []
        after_artifacts, after_error = self._capture_artifacts(
            run_id=run_id,
            step=step,
            context=context,
            phase="finalize",
            reason="after-action",
            enabled=step.evidence_policy.capture_after,
        )
        finalize_artifacts.extend(after_artifacts)
        if after_error:
            finalize_errors.append(after_error)

        if self._is_failed_result(action_result, state.failure_category):
            failure_artifacts, failure_error = self._capture_artifacts(
                run_id=run_id,
                step=step,
                context=context,
                phase="finalize",
                reason="failure",
                enabled=step.evidence_policy.capture_on_failure,
            )
            finalize_artifacts.extend(failure_artifacts)
            if failure_error:
                finalize_errors.append(failure_error)

        if finalize_errors:
            state.artifact_error_message = "; ".join(finalize_errors)
        self._append_phase_report(
            state,
            step=step,
            phase="finalize",
            status="failed" if finalize_errors else "passed",
            failure_category="artifact_error" if finalize_errors else None,
            error_message="; ".join(finalize_errors) if finalize_errors else None,
            artifact_refs=finalize_artifacts,
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="finalize")

    def _run_common_step(
        self,
        run_id: str,
        step: ExecutableStep,
        capability: CapabilityDefinition,
        state: _StepExecutionState,
    ) -> RunnerStepResult:
        self._record_passed_empty_phase(run_id, step, state, "prepare")
        status = self._run_common_invoke_phase(run_id, step, capability, state)
        self._record_passed_empty_phase(run_id, step, state, "finalize")
        return self._finish_step(
            run_id,
            step,
            state,
            status=status,
            failure_category=state.failure_category,
            error_message=state.error_message,
        )

    def _run_common_invoke_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        capability: CapabilityDefinition,
        state: _StepExecutionState,
    ) -> RunnerStatus:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="invoke")
        metadata: dict[str, object] = {}
        status: RunnerStatus = "passed"
        try:
            result = self._execute_common_capability(step, capability)
            status = result.status
            state.failure_category = result.failure_category
            state.error_message = result.error_message
            self._last_capability_execution_result = result
            metadata = self._common_result_metadata(result)
        except Exception as exc:  # noqa: BLE001 - common capability failures are reported as structured step failures.
            status = "failed"
            state.failure_category = "configuration_error"
            state.error_message = str(exc) or exc.__class__.__name__
        if status in {"failed", "cancelled", "skipped"} or state.failure_category:
            self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
        self._append_phase_report(
            state,
            step=step,
            phase="invoke",
            status=status,
            duration_ms=metadata.get("duration_ms", 0) if isinstance(metadata.get("duration_ms"), int) else 0,
            failure_category=state.failure_category,
            error_message=state.error_message,
            metadata=metadata,
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="invoke")
        return status

    def _record_passed_empty_phase(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        phase: StepPhase,
    ) -> None:
        self._emit(run_id=run_id, event_type="phase_start", step=step, phase=phase)
        self._append_phase_report(state, step=step, phase=phase, status="passed")
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase=phase)

    def _append_phase_report(
        self,
        state: _StepExecutionState,
        *,
        step: ExecutableStep,
        phase: StepPhase,
        status: RunnerStatus,
        duration_ms: int = 0,
        failure_category: FailureCategory | None = None,
        error_message: str | None = None,
        artifact_refs: list[EvidenceArtifactRef] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        state.phase_reports.append(
            StepPhaseReport(
                step_id=step.step_id,
                phase=phase,
                status=status,
                duration_ms=duration_ms,
                failure_category=failure_category,
                error_message=error_message,
                artifact_refs=artifact_refs or [],
                metadata=metadata or {},
            )
        )

    def _finish_step(
        self,
        run_id: str,
        step: ExecutableStep,
        state: _StepExecutionState,
        *,
        status: RunnerStatus,
        failure_category: FailureCategory | None,
        error_message: str | None,
    ) -> RunnerStepResult:
        self._emit(run_id=run_id, event_type="step_finish", step=step)
        return RunnerStepResult(
            step_id=step.step_id,
            source_ref=step.source_ref,
            status=status,
            duration_ms=self._duration_ms(state.started),
            phase_reports=state.phase_reports,
            max_attempts=step.retry_policy.max_attempts,
            failure_category=failure_category,
            error_message=error_message,
        )

    def _execute_common_capability(self, step: ExecutableStep, capability: CapabilityDefinition) -> CapabilityExecutionResult:
        executor = self.executor_bindings.common_executor(capability.name)
        if executor is None:
            return CapabilityExecutionResult(
                capability_name=capability.name,
                executor_kind="common",
                status="failed",
                failure_category="configuration_error",
                error_message=f"No executor is bound for common capability: {capability.name}",
            )
        result = executor(step)
        if hasattr(result, "__await__"):
            raise RuntimeError("Async common capability executors are not supported by synchronous StepRunner.")
        return result

    def _common_result_metadata(self, result: CapabilityExecutionResult) -> dict[str, object]:
        metadata: dict[str, object] = dict(result.metadata)
        metadata["capability_name"] = result.capability_name
        metadata["executor_kind"] = result.executor_kind
        metadata["sensitivity"] = result.sensitivity
        if result.replay is not None:
            metadata["replay"] = result.replay.model_dump(mode="json")
        if result.safe_replay_params:
            metadata["safe_replay_params"] = dict(result.safe_replay_params)
        if result.output is not None and not result.sensitivity:
            metadata["common_output"] = result.output
        if result.sensitivity:
            metadata["common_output_redacted"] = True
        metadata.setdefault("duration_ms", result.duration_ms)
        return metadata

    def _emit(
        self,
        *,
        run_id: str,
        event_type: RunnerEventType,
        step: ExecutableStep,
        phase: StepPhase | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        self._events.append(
            RunnerEvent(
                event_type=event_type,
                run_id=run_id,
                step_id=step.step_id,
                phase=phase,
                payload=payload or {},
            )
        )

    def _capture_artifacts(
        self,
        *,
        run_id: str,
        step: ExecutableStep,
        context: object,
        phase: StepPhase,
        reason: str,
        enabled: bool,
    ) -> tuple[list[EvidenceArtifactRef], str | None]:
        if not enabled or not step.evidence_policy.artifact_kinds:
            return [], None

        refs: list[EvidenceArtifactRef] = []
        for kind in step.evidence_policy.artifact_kinds:
            try:
                harness_ref = self.harness.capture_artifact(
                    kind=kind,
                    reason=reason,
                    context=context,
                    step_id=step.step_id,
                    phase=phase,
                )
            except Exception as exc:  # noqa: BLE001 - artifact capture failures are recorded as phase facts.
                return refs, str(exc)
            ref = self._to_evidence_artifact_ref(harness_ref, step.step_id, phase)
            refs.append(ref)
            self._emit(
                run_id=run_id,
                event_type="artifact_captured",
                step=step,
                phase=phase,
                payload={
                    "artifact_id": ref.artifact_id,
                    "kind": ref.kind,
                    "path": ref.path.as_posix(),
                    "reason": reason,
                    "phase": phase,
                },
            )
        return refs, None

    def _to_evidence_artifact_ref(
        self,
        ref: HarnessArtifactRef,
        step_id: str,
        phase: StepPhase,
    ) -> EvidenceArtifactRef:
        return EvidenceArtifactRef(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            path=ref.path,
            mime_type=ref.mime_type,
            created_at=ref.created_at,
            step_id=step_id,
            phase=phase,
            metadata=dict(ref.metadata),
        )

    def _action_result_artifacts(
        self,
        run_id: str,
        step: ExecutableStep,
        action_result: HarnessActionResult,
        phase: StepPhase,
    ) -> list[EvidenceArtifactRef]:
        refs: list[EvidenceArtifactRef] = []
        for harness_ref in action_result.artifact_refs:
            ref = self._to_evidence_artifact_ref(harness_ref, step.step_id, phase)
            refs.append(ref)
            self._emit(
                run_id=run_id,
                event_type="artifact_captured",
                step=step,
                phase=phase,
                payload={
                    "artifact_id": ref.artifact_id,
                    "kind": ref.kind,
                    "path": ref.path.as_posix(),
                    "reason": "action-result",
                    "phase": phase,
                },
            )
        return refs

    def _action_result_metadata(self, action_result: HarnessActionResult) -> dict[str, object]:
        metadata: dict[str, object] = {}
        if action_result.metadata:
            metadata["harness_metadata"] = action_result.metadata
        if action_result.output is not None:
            metadata["harness_output"] = action_result.output
        return metadata

    def _is_failed_result(
        self,
        action_result: HarnessActionResult | None,
        failure_category: FailureCategory | None,
    ) -> bool:
        return bool(failure_category) or bool(action_result and action_result.status in {"failed", "cancelled", "skipped"})

    def _result_status(
        self,
        action_result: HarnessActionResult | None,
        failure_category: FailureCategory | None,
        artifact_error_message: str | None,
    ) -> RunnerStatus:
        if artifact_error_message:
            return "failed"
        if action_result and action_result.status in {"failed", "cancelled", "skipped"}:
            return action_result.status
        if failure_category:
            return "failed"
        return "passed"

    def _duration_ms(self, started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))
