import json
from pathlib import Path

from fsq_agent.models import (
    EvidenceArtifactRef,
    EvidenceBundle,
    RunnerEvent,
    RunnerStepResult,
    StepPhaseReport,
)
from fsq_agent.report import CoreEvidenceReportGenerator


def test_core_evidence_report_generator_writes_markdown_and_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "evidence-manifest.json"
    bundle = EvidenceBundle(
        bundle_id="run-1-evidence",
        run_id="run-1",
        manifest_path=manifest_path,
        events=[
            RunnerEvent(run_id="run-1", event_type="step_start", step_id="step-1"),
            RunnerEvent(run_id="run-1", event_type="step_error", step_id="step-2", phase="invoke"),
        ],
        steps=[
            RunnerStepResult(
                step_id="step-1",
                status="passed",
                phase_reports=[StepPhaseReport(step_id="step-1", phase="invoke", status="passed")],
            ),
            RunnerStepResult(
                step_id="step-2",
                status="failed",
                failure_category="target_resolution_error",
                error_message="Target was not found.",
                phase_reports=[
                    StepPhaseReport(step_id="step-2", phase="prepare", status="passed"),
                    StepPhaseReport(
                        step_id="step-2",
                        phase="invoke",
                        status="failed",
                        failure_category="target_resolution_error",
                        error_message="Target was not found.",
                    ),
                ],
            ),
        ],
        artifacts=[
            EvidenceArtifactRef(
                artifact_id="step-2-finalize-failure",
                kind="screenshot",
                path=Path("artifacts/screenshots/step-2-finalize-failure.png"),
                step_id="step-2",
                phase="finalize",
            )
        ],
        metadata={"case_id": "case-1", "source_path": "cases/case-1.codex.yaml"},
    )
    manifest_path.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2), encoding="utf-8")

    artifact = CoreEvidenceReportGenerator().generate_from_manifest(manifest_path)

    assert artifact.run_id == "run-1"
    assert artifact.path == tmp_path / "core-report.md"
    assert artifact.evidence_manifest_path == manifest_path
    assert artifact.path.exists()
    json_report_path = tmp_path / "core-report.json"
    assert json_report_path.exists()

    markdown = artifact.path.read_text(encoding="utf-8")
    assert "# Core Evidence Report: run-1" in markdown
    assert "Status: `failed`" in markdown
    assert "`step-2`" in markdown
    assert "target_resolution_error" in markdown
    assert "artifacts/screenshots/step-2-finalize-failure.png" in markdown

    payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-1"
    assert payload["summary"] == {
        "status": "failed",
        "step_count": 2,
        "passed_steps": 1,
        "failed_steps": 1,
        "artifact_count": 1,
    }
    assert payload["steps"][1]["failure_category"] == "target_resolution_error"
    assert payload["events"][1]["event_type"] == "step_error"
    assert payload["artifacts"][0]["path"] == "artifacts/screenshots/step-2-finalize-failure.png"
