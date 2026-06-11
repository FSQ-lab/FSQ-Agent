import time
from collections.abc import Sequence

from fsq_agent.core.harness import HarnessInterface
from fsq_agent.models import (
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


class StepRunner:
    def __init__(self, harness: HarnessInterface) -> None:
        self.harness = harness
        self._events: list[RunnerEvent] = []

    @property
    def events(self) -> Sequence[RunnerEvent]:
        return tuple(self._events)

    def run_step(self, run_id: str, step: ExecutableStep) -> RunnerStepResult:
        started = time.perf_counter()
        phase_reports: list[StepPhaseReport] = []
        self._emit(run_id=run_id, event_type="step_start", step=step)
        artifact_error_message: str | None = None

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
            artifact_error_message = prepare_error
        self.harness.before_action(step, context)
        phase_reports.append(
            StepPhaseReport(
                step_id=step.step_id,
                phase="prepare",
                status="failed" if prepare_error else "passed",
                failure_category="artifact_error" if prepare_error else None,
                error_message=prepare_error,
                artifact_refs=prepare_artifacts,
            )
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="prepare")

        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="invoke")
        self._emit(run_id=run_id, event_type="harness_call_start", step=step, phase="invoke")
        action_result: HarnessActionResult | None = None
        failure_category: FailureCategory | None = None
        error_message: str | None = None
        try:
            action_result = self.harness.invoke_action(step, context)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            if action_result.status in {"failed", "cancelled", "skipped"}:
                failure_category = action_result.failure_category
                error_message = action_result.error_message
                self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            phase_reports.append(
                StepPhaseReport(
                    step_id=step.step_id,
                    phase="invoke",
                    status=action_result.status,
                    artifact_refs=self._action_result_artifacts(run_id, step, action_result, "invoke"),
                )
            )
        except Exception as exc:  # noqa: BLE001 - runner converts phase exceptions into structured results.
            failure_category = self.harness.classify_error(exc, "invoke", step)
            error_message = str(exc)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            self._emit(run_id=run_id, event_type="step_error", step=step, phase="invoke")
            phase_reports.append(
                StepPhaseReport(
                    step_id=step.step_id,
                    phase="invoke",
                    status="failed",
                    failure_category=failure_category,
                    error_message=error_message,
                )
            )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="invoke")

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

        if self._is_failed_result(action_result, failure_category):
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
            artifact_error_message = "; ".join(finalize_errors)
        phase_reports.append(
            StepPhaseReport(
                step_id=step.step_id,
                phase="finalize",
                status="failed" if finalize_errors else "passed",
                failure_category="artifact_error" if finalize_errors else None,
                error_message="; ".join(finalize_errors) if finalize_errors else None,
                artifact_refs=finalize_artifacts,
            )
        )
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="finalize")

        self._emit(run_id=run_id, event_type="step_finish", step=step)
        status = self._result_status(action_result, failure_category, artifact_error_message)
        return RunnerStepResult(
            step_id=step.step_id,
            source_ref=step.source_ref,
            status=status,
            duration_ms=self._duration_ms(started),
            phase_reports=phase_reports,
            max_attempts=step.retry_policy.max_attempts,
            failure_category="artifact_error" if artifact_error_message else failure_category,
            error_message=artifact_error_message or error_message,
        )

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
