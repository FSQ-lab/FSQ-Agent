import json
from pathlib import Path
from typing import Any

import pytest

from fsq_agent.cli._core_execution import run_fsq_core_case, run_strict_fsq_core_case
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


FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Core CLI Case
platform: android
appId: com.microsoft.emmx
---
- launchApp
- tapOn:
    target: Search box
"""


FSQ_CASE_WITH_TEARDOWN = """
schemaVersion: fsq.ai-test/v1
name: Core CLI Teardown Case
platform: android
appId: com.microsoft.emmx
---
- launchApp
- tapOn:
    target: Search box
- inputText:
    text: skipped
    target: Search box
- killApp
"""


class CliCoreHarness:
    def __init__(self, fail_action: str | None = None) -> None:
        self.fail_action = fail_action
        self.actions: list[str] = []

    def get_context(self) -> HarnessContext:
        return HarnessContext(platform="android", session_id="session-1")

    def action_space(self) -> dict[str, Any]:
        return {}

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        return None

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        self.actions.append(step.action_name)
        status = "failed" if step.action_name == self.fail_action else "passed"
        return HarnessActionResult(
            status=status,
            action_name=step.action_name,
            failure_category="target_resolution_error" if status == "failed" else None,
            error_message="Target was not found." if status == "failed" else None,
        )

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


def test_run_fsq_core_case_runs_trailing_teardown_after_failure(tmp_path: Path) -> None:
    case_path = tmp_path / "core_cli_teardown.codex.yaml"
    case_path.write_text(FSQ_CASE_WITH_TEARDOWN, encoding="utf-8")
    harness = CliCoreHarness(fail_action="tapOn")

    bundle = run_fsq_core_case(
        case_path=case_path,
        harness=harness,
        output_dir=tmp_path / "runs" / "run-1",
        run_id="run-1",
    )

    assert harness.actions == ["launchApp", "tapOn", "killApp"]
    assert [step.step_id for step in bundle.steps] == [
        "core_cli_teardown-step-001",
        "core_cli_teardown-step-002",
        "core_cli_teardown-step-004",
    ]
    assert [step.status for step in bundle.steps] == ["passed", "failed", "passed"]

    manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
    assert [step["step_id"] for step in manifest["steps"]] == [
        "core_cli_teardown-step-001",
        "core_cli_teardown-step-002",
        "core_cli_teardown-step-004",
    ]


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
