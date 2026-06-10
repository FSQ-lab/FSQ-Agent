import json
from pathlib import Path
from typing import Any

from fsq_agent.cli._core_execution import run_fsq_core_case, run_strict_fsq_core_case
from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    StepPhase,
)


FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Core CLI Case
platform: android
appId: com.microsoft.emmx
---
- launchApp
- tapOn: Search box
"""


class CliCoreHarness:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def get_context(self) -> HarnessContext:
        return HarnessContext(platform="android", session_id="session-1")

    def action_space(self) -> dict[str, Any]:
        return {}

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        return None

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.actions.append(step.action_name)
        return HarnessActionResult(status="passed", action_name=step.action_name)

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        return None

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        return HarnessArtifactRef(
            artifact_id=f"{step_id}-{phase}-{kind}",
            kind=kind,
            path=Path(f"artifacts/raw/{step_id}-{phase}-{reason}.{kind}"),
        )

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        return "unknown"


def test_run_fsq_core_case_writes_manifest_and_returns_bundle(tmp_path: Path) -> None:
    case_path = tmp_path / "core_cli.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    harness = CliCoreHarness()

    bundle = run_fsq_core_case(
        case_path=case_path,
        harness=harness,
        output_dir=tmp_path / "runs" / "run-1",
        run_id="run-1",
    )

    assert bundle.run_id == "run-1"
    assert bundle.manifest_path == tmp_path / "runs" / "run-1" / "evidence-manifest.json"
    assert bundle.manifest_path.exists()
    assert harness.actions == ["launchApp", "tapOn"]
    assert [step.step_id for step in bundle.steps] == ["core_cli-step-001", "core_cli-step-002"]

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert manifest["run_id"] == "run-1"
    assert manifest["manifest_path"] == str(bundle.manifest_path)
    assert [step["step_id"] for step in manifest["steps"]] == ["core_cli-step-001", "core_cli-step-002"]
    assert [step["status"] for step in manifest["steps"]] == ["passed", "passed"]
    assert [event["event_type"] for event in manifest["events"]].count("step_start") == 2


def test_run_strict_fsq_core_case_writes_evidence_and_core_report(tmp_path: Path) -> None:
    case_path = tmp_path / "strict_core.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    run_dir = tmp_path / "runs" / "strict-run-1"

    artifact = run_strict_fsq_core_case(
        case_path=case_path,
        harness=CliCoreHarness(),
        output_dir=run_dir,
        run_id="strict-run-1",
    )

    assert artifact.run_id == "strict-run-1"
    assert artifact.path == run_dir / "core-report.md"
    assert artifact.evidence_manifest_path == run_dir / "evidence-manifest.json"
    assert artifact.path.exists()
    assert (run_dir / "core-report.json").exists()

    report = artifact.path.read_text(encoding="utf-8")
    assert "# Core Evidence Report: strict-run-1" in report
    assert "Status: `passed`" in report

    manifest = json.loads((run_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
    assert [step["status"] for step in manifest["steps"]] == ["passed", "passed"]
