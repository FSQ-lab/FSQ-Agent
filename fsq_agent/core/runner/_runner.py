import time
from collections.abc import Sequence

from fsq_agent.core.harness import HarnessInterface
from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    RunnerEvent,
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

        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="prepare")
        context = self.harness.get_context()
        self.harness.before_action(step, context)
        phase_reports.append(StepPhaseReport(step_id=step.step_id, phase="prepare", status="passed"))
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="prepare")

        self._emit(run_id=run_id, event_type="phase_start", step=step, phase="invoke")
        self._emit(run_id=run_id, event_type="harness_call_start", step=step, phase="invoke")
        action_result: HarnessActionResult | None = None
        failure_category: FailureCategory | None = None
        error_message: str | None = None
        try:
            action_result = self.harness.invoke_action(step, context)
            self._emit(run_id=run_id, event_type="harness_call_finish", step=step, phase="invoke")
            phase_reports.append(StepPhaseReport(step_id=step.step_id, phase="invoke", status=action_result.status))
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
        phase_reports.append(StepPhaseReport(step_id=step.step_id, phase="finalize", status="passed"))
        self._emit(run_id=run_id, event_type="phase_finish", step=step, phase="finalize")

        self._emit(run_id=run_id, event_type="step_finish", step=step)
        return RunnerStepResult(
            step_id=step.step_id,
            source_ref=step.source_ref,
            status="failed" if failure_category else "passed",
            duration_ms=self._duration_ms(started),
            phase_reports=phase_reports,
            max_attempts=step.retry_policy.max_attempts,
            failure_category=failure_category,
            error_message=error_message,
        )

    def _emit(
        self,
        *,
        run_id: str,
        event_type: str,
        step: ExecutableStep,
        phase: StepPhase | None = None,
    ) -> None:
        self._events.append(
            RunnerEvent(
                event_type=event_type,
                run_id=run_id,
                step_id=step.step_id,
                phase=phase,
            )
        )

    def _duration_ms(self, started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))
