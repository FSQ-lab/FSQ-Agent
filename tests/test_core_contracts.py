from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fsq_agent.models import (
    EvidenceArtifactRef,
    EvidenceBundle,
    EvidencePolicy,
    ExecutableStep,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    RetryPolicy,
    RunnerEvent,
    RunnerStepResult,
    SourceRef,
    StepPhaseReport,
)


def test_core_exports_harness_interface() -> None:
    from fsq_agent.core import HarnessInterface

    assert HarnessInterface.__name__ == "HarnessInterface"


def test_fake_harness_satisfies_runtime_protocol() -> None:
    from fsq_agent.core.harness import HarnessInterface

    class FakeHarness:
        def get_context(self) -> HarnessContext:
            return HarnessContext(platform="android", session_id="session-1")

        def action_space(self) -> dict[str, object]:
            return {"tap": {"description": "Tap an element"}}

        def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
            return None

        def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
            return HarnessActionResult(status="passed", action_name=step.action_name)

        def after_action(
            self,
            step: ExecutableStep,
            context: HarnessContext,
            action_result: HarnessActionResult,
        ) -> None:
            return None

        def capture_artifact(
            self,
            kind: str,
            reason: str,
            context: HarnessContext,
            step_id: str,
            phase: str,
        ) -> HarnessArtifactRef:
            return HarnessArtifactRef(artifact_id=f"{kind}-1", kind="log", path=Path(f"runs/run-1/{step_id}-{phase}-{reason}.log"))

        def classify_error(self, error: BaseException, phase: str, step: ExecutableStep) -> str:
            return "unknown"

    assert isinstance(FakeHarness(), HarnessInterface)


def test_executable_step_accepts_contract_fields() -> None:
    step = ExecutableStep(
        step_id="step-1",
        source_ref=SourceRef(source_type="fsq", source_id="case.yaml", step_index=1),
        kind="action",
        action_name="tap",
        params={"text": "Login"},
        target_ref="button:login",
        retry_policy=RetryPolicy(max_attempts=2),
        evidence_policy=EvidencePolicy(capture_before=True, capture_after=True),
        timeout_ms=5000,
        metadata={"owner": "test"},
    )

    assert step.step_id == "step-1"
    assert step.kind == "action"
    assert step.retry_policy.max_attempts == 2
    assert step.evidence_policy.capture_after is True


def test_executable_step_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        ExecutableStep(step_id="step-1", kind="unknown", action_name="tap")


def test_phase_report_preserves_phase_failure_boundary() -> None:
    report = StepPhaseReport(
        step_id="step-1",
        phase="prepare",
        status="failed",
        duration_ms=12,
        failure_category="context_error",
        error_message="context unavailable",
    )

    assert report.phase == "prepare"
    assert report.failure_category == "context_error"


def test_runner_event_requires_known_event_type() -> None:
    with pytest.raises(ValidationError):
        RunnerEvent(run_id="run-1", event_type="unknown", payload={})


def test_evidence_bundle_serializes_artifact_refs_without_binary_payloads() -> None:
    created_at = datetime.now(timezone.utc)
    artifact = EvidenceArtifactRef(
        artifact_id="artifact-1",
        kind="screenshot",
        path=Path("runs/run-1/screenshot.png"),
        mime_type="image/png",
        created_at=created_at,
        step_id="step-1",
        phase="finalize",
    )
    bundle = EvidenceBundle(
        bundle_id="bundle-1",
        run_id="run-1",
        created_at=created_at,
        manifest_path=Path("runs/run-1/evidence.json"),
        artifacts=[artifact],
    )

    payload = bundle.model_dump(mode="json")

    assert payload["artifacts"][0]["path"] == "runs/run-1/screenshot.png"
    assert "bytes" not in payload["artifacts"][0]


def test_runner_step_result_uses_distinct_name_from_legacy_step_result() -> None:
    result = RunnerStepResult(
        step_id="step-1",
        status="passed",
        phase_reports=[StepPhaseReport(step_id="step-1", phase="invoke", status="passed")],
    )

    assert result.status == "passed"
    assert result.phase_reports[0].phase == "invoke"


def test_harness_models_capture_context_action_and_artifacts() -> None:
    artifact = HarnessArtifactRef(artifact_id="artifact-1", kind="log", path=Path("runs/run-1/action.log"))
    context = HarnessContext(platform="android", session_id="session-1", current_activity="MainActivity")
    result = HarnessActionResult(status="passed", action_name="tap", artifact_refs=[artifact])

    assert context.platform == "android"
    assert result.artifact_refs[0].kind == "log"
