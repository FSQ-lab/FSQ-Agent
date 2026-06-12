from pathlib import Path
from typing import Any

import pytest

from fsq_agent.core import EvidenceRecorder, StepSequenceRunner
import fsq_agent.core.runner._sequence as sequence_module
from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    StepPhase,
)


@pytest.fixture(autouse=True)
def _skip_real_sequence_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sequence_module.time, "sleep", lambda seconds: None)


class SequenceHarness:
    def __init__(self, fail_action: str | None = None) -> None:
        self.fail_action = fail_action
        self.calls: list[str] = []

    def get_context(self) -> HarnessContext:
        self.calls.append("get_context")
        return HarnessContext(platform="android", session_id="session-1")

    def action_space(self) -> dict[str, Any]:
        return {}

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        self.calls.append(f"before:{step.step_id}")

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.calls.append(f"invoke:{step.step_id}")
        status = "failed" if step.action_name == self.fail_action else "passed"
        return HarnessActionResult(status=status, action_name=step.action_name)

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        self.calls.append(f"after:{step.step_id}:{action_result.status if action_result else 'none'}")

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        return HarnessArtifactRef(artifact_id=f"{kind}-1", kind="log", path=Path(f"runs/{step_id}-{phase}-{reason}.log"))

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        return "unknown"


def _step(step_id: str, action_name: str) -> ExecutableStep:
    return ExecutableStep(step_id=step_id, kind="action", action_name=action_name)


def test_step_sequence_runner_runs_steps_in_order_and_records_evidence(tmp_path: Path) -> None:
    harness = SequenceHarness()
    recorder = EvidenceRecorder(run_id="run-1", output_dir=tmp_path)
    runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder)

    bundle = runner.run_steps(run_id="run-1", steps=[_step("step-1", "tapOn"), _step("step-2", "inputText")])

    assert [step.step_id for step in bundle.steps] == ["step-1", "step-2"]
    assert [step.status for step in bundle.steps] == ["passed", "passed"]
    assert [event.event_type for event in bundle.events].count("step_start") == 2
    assert harness.calls == [
        "get_context",
        "before:step-1",
        "invoke:step-1",
        "after:step-1:passed",
        "get_context",
        "before:step-2",
        "invoke:step-2",
        "after:step-2:passed",
    ]


def test_step_sequence_runner_stops_after_first_failed_step(tmp_path: Path) -> None:
    harness = SequenceHarness(fail_action="tapOn")
    recorder = EvidenceRecorder(run_id="run-1", output_dir=tmp_path)
    runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder)

    bundle = runner.run_steps(run_id="run-1", steps=[_step("step-1", "tapOn"), _step("step-2", "inputText")])

    assert [step.step_id for step in bundle.steps] == ["step-1"]
    assert bundle.steps[0].status == "failed"
    assert "before:step-2" not in harness.calls


def test_step_sequence_runner_runs_teardown_after_failed_normal_step(tmp_path: Path) -> None:
    harness = SequenceHarness(fail_action="tapOn")
    recorder = EvidenceRecorder(run_id="run-1", output_dir=tmp_path)
    runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder)

    bundle = runner.run_steps(
        run_id="run-1",
        steps=[_step("step-1", "tapOn"), _step("step-2", "inputText")],
        teardown_steps=[_step("teardown-1", "killApp")],
    )

    assert [step.step_id for step in bundle.steps] == ["step-1", "teardown-1"]
    assert [step.status for step in bundle.steps] == ["failed", "passed"]
    assert "before:step-2" not in harness.calls
    assert harness.calls == [
        "get_context",
        "before:step-1",
        "invoke:step-1",
        "after:step-1:failed",
        "get_context",
        "before:teardown-1",
        "invoke:teardown-1",
        "after:teardown-1:passed",
    ]


def test_step_sequence_runner_runs_teardown_after_successful_normal_steps(tmp_path: Path) -> None:
    harness = SequenceHarness()
    recorder = EvidenceRecorder(run_id="run-1", output_dir=tmp_path)
    runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder)

    bundle = runner.run_steps(
        run_id="run-1",
        steps=[_step("step-1", "tapOn")],
        teardown_steps=[_step("teardown-1", "killApp")],
    )

    assert [step.step_id for step in bundle.steps] == ["step-1", "teardown-1"]
    assert [step.status for step in bundle.steps] == ["passed", "passed"]


def test_step_sequence_runner_waits_between_executed_steps_without_evidence_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = SequenceHarness()
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        harness.calls.append(f"sleep:{seconds}")

    monkeypatch.setattr(sequence_module.time, "sleep", fake_sleep)

    recorder = EvidenceRecorder(run_id="run-1", output_dir=tmp_path)
    runner = StepSequenceRunner(harness=harness, evidence_recorder=recorder)

    bundle = runner.run_steps(
        run_id="run-1",
        steps=[_step("step-1", "tapOn"), _step("step-2", "inputText")],
        teardown_steps=[_step("teardown-1", "killApp")],
    )

    assert sleep_calls == [1.0, 1.0]
    assert [step.step_id for step in bundle.steps] == ["step-1", "step-2", "teardown-1"]
    assert [event.event_type for event in bundle.events].count("step_start") == 3
    assert harness.calls == [
        "get_context",
        "before:step-1",
        "invoke:step-1",
        "after:step-1:passed",
        "sleep:1",
        "get_context",
        "before:step-2",
        "invoke:step-2",
        "after:step-2:passed",
        "sleep:1",
        "get_context",
        "before:teardown-1",
        "invoke:teardown-1",
        "after:teardown-1:passed",
    ]
