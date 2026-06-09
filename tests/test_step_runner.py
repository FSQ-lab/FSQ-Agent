from pathlib import Path
from typing import Any

from fsq_agent.core import StepRunner
from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    StepPhase,
)


class SuccessfulHarness:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_context(self) -> HarnessContext:
        self.calls.append("get_context")
        return HarnessContext(platform="android", session_id="session-1")

    def action_space(self) -> dict[str, Any]:
        return {"tap": {"description": "Tap an element"}}

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        self.calls.append(f"before:{step.action_name}:{context.session_id}")

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.calls.append(f"invoke:{step.action_name}:{context.session_id}")
        return HarnessActionResult(status="passed", action_name=step.action_name, output={"ok": True})

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        status = action_result.status if action_result else "none"
        self.calls.append(f"after:{step.action_name}:{status}")

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        return HarnessArtifactRef(artifact_id=f"{kind}-1", kind="log", path=Path(f"runs/run-1/{step_id}-{phase}-{reason}.log"))

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        return "unknown"


class InvokeFailureHarness(SuccessfulHarness):
    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.calls.append(f"invoke:{step.action_name}:{context.session_id}")
        raise RuntimeError("tap failed")

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        status = action_result.status if action_result else "none"
        self.calls.append(f"after:{step.action_name}:{status}")

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        self.calls.append(f"classify:{phase}:{step.action_name}:{type(error).__name__}")
        return "action_error"


def _tap_step() -> ExecutableStep:
    return ExecutableStep(
        step_id="step-1",
        kind="action",
        action_name="tap",
        params={"text": "Login"},
    )


def test_step_runner_runs_successful_step_through_three_phases() -> None:
    harness = SuccessfulHarness()
    runner = StepRunner(harness=harness)

    result = runner.run_step(run_id="run-1", step=_tap_step())

    assert result.step_id == "step-1"
    assert result.status == "passed"
    assert [phase.phase for phase in result.phase_reports] == ["prepare", "invoke", "finalize"]
    assert [phase.status for phase in result.phase_reports] == ["passed", "passed", "passed"]
    assert harness.calls == [
        "get_context",
        "before:tap:session-1",
        "invoke:tap:session-1",
        "after:tap:passed",
    ]
    assert [event.event_type for event in runner.events] == [
        "step_start",
        "phase_start",
        "phase_finish",
        "phase_start",
        "harness_call_start",
        "harness_call_finish",
        "phase_finish",
        "phase_start",
        "phase_finish",
        "step_finish",
    ]


def test_step_runner_wraps_invoke_exception_and_still_finalizes() -> None:
    harness = InvokeFailureHarness()
    runner = StepRunner(harness=harness)

    result = runner.run_step(run_id="run-1", step=_tap_step())

    assert result.status == "failed"
    assert result.failure_category == "action_error"
    assert result.error_message == "tap failed"
    assert [phase.phase for phase in result.phase_reports] == ["prepare", "invoke", "finalize"]
    assert [phase.status for phase in result.phase_reports] == ["passed", "failed", "passed"]
    invoke_report = result.phase_reports[1]
    assert invoke_report.failure_category == "action_error"
    assert invoke_report.error_message == "tap failed"
    assert harness.calls == [
        "get_context",
        "before:tap:session-1",
        "invoke:tap:session-1",
        "classify:invoke:tap:RuntimeError",
        "after:tap:none",
    ]
    assert "step_error" in [event.event_type for event in runner.events]
    assert runner.events[-1].event_type == "step_finish"
