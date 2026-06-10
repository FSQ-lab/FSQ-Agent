from pathlib import Path
from typing import Any

from fsq_agent.core import StepRunner
from fsq_agent.models import (
    EvidencePolicy,
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


class FailedResultHarness(SuccessfulHarness):
    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.calls.append(f"invoke:{step.action_name}:{context.session_id}")
        return HarnessActionResult(
            status="failed",
            action_name=step.action_name,
            failure_category="target_resolution_error",
            error_message="target not found",
        )


class CapturingHarness(SuccessfulHarness):
    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        self.calls.append(f"capture:{kind}:{reason}:{step_id}:{phase}")
        return HarnessArtifactRef(
            artifact_id=f"{step_id}-{phase}-{reason}-{kind}",
            kind=kind,
            path=Path(f"artifacts/{kind}/{step_id}-{phase}-{reason}.{kind}"),
        )


class FailingCaptureHarness(SuccessfulHarness):
    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        self.calls.append(f"capture:{kind}:{reason}:{step_id}:{phase}")
        raise RuntimeError("capture failed")


class FailedCapturingHarness(CapturingHarness):
    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.calls.append(f"invoke:{step.action_name}:{context.session_id}")
        return HarnessActionResult(
            status="failed",
            action_name=step.action_name,
            failure_category="target_resolution_error",
            error_message="target not found",
        )


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


def test_step_runner_preserves_failed_harness_action_result() -> None:
    harness = FailedResultHarness()
    runner = StepRunner(harness=harness)

    result = runner.run_step(run_id="run-1", step=_tap_step())

    assert result.status == "failed"
    assert result.failure_category == "target_resolution_error"
    assert result.error_message == "target not found"
    assert [phase.status for phase in result.phase_reports] == ["passed", "failed", "passed"]
    assert "step_error" in [event.event_type for event in runner.events]


def test_step_runner_captures_before_and_after_artifacts_from_policy() -> None:
    harness = CapturingHarness()
    runner = StepRunner(harness=harness)
    step = ExecutableStep(
        step_id="step-1",
        kind="action",
        action_name="tap",
        evidence_policy=EvidencePolicy(
            capture_before=True,
            capture_after=True,
            artifact_kinds=["screenshot", "ui_tree"],
        ),
    )

    result = runner.run_step(run_id="run-1", step=step)

    prepare_report = result.phase_reports[0]
    finalize_report = result.phase_reports[2]
    assert [artifact.kind for artifact in prepare_report.artifact_refs] == ["screenshot", "ui_tree"]
    assert [artifact.kind for artifact in finalize_report.artifact_refs] == ["screenshot", "ui_tree"]
    assert [event.event_type for event in runner.events].count("artifact_captured") == 4
    assert "capture:screenshot:before-action:step-1:prepare" in harness.calls
    assert "capture:ui_tree:after-action:step-1:finalize" in harness.calls


def test_step_runner_captures_failure_artifacts_from_policy() -> None:
    harness = CapturingHarness()
    runner = StepRunner(harness=harness)
    step = ExecutableStep(
        step_id="step-1",
        kind="action",
        action_name="tap",
        evidence_policy=EvidencePolicy(capture_after=False, capture_on_failure=True, artifact_kinds=["screenshot"]),
    )

    result = runner.run_step(run_id="run-1", step=step)

    assert result.status == "passed"
    assert [artifact.kind for artifact in result.phase_reports[2].artifact_refs] == []

    failed_harness = FailedCapturingHarness()
    failed_runner = StepRunner(harness=failed_harness)
    failed_result = failed_runner.run_step(run_id="run-1", step=step)

    assert failed_result.status == "failed"
    assert [artifact.kind for artifact in failed_result.phase_reports[2].artifact_refs] == ["screenshot"]
    assert "capture:screenshot:failure:step-1:finalize" in failed_harness.calls


def test_step_runner_reports_artifact_capture_errors_without_crashing() -> None:
    harness = FailingCaptureHarness()
    runner = StepRunner(harness=harness)
    step = ExecutableStep(
        step_id="step-1",
        kind="action",
        action_name="tap",
        evidence_policy=EvidencePolicy(capture_after=True, artifact_kinds=["screenshot"]),
    )

    result = runner.run_step(run_id="run-1", step=step)

    finalize_report = result.phase_reports[2]
    assert result.status == "failed"
    assert finalize_report.status == "failed"
    assert finalize_report.failure_category == "artifact_error"
    assert finalize_report.error_message == "capture failed"
