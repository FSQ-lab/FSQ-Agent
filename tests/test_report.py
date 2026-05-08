import json
from pathlib import Path

import pytest

from fsq_agent.models import StepResult, Task, VerificationResult
from fsq_agent.report import ReportGenerator


class _FailingRichReportGenerator(ReportGenerator):
    def _write_rich_reports(
        self,
        report_dir: Path,
        report_path: Path,
        task: Task,
        steps: list[StepResult],
        verification: VerificationResult,
    ) -> None:
        raise OSError("simulated rich report failure")


def _task() -> Task:
    return Task(
        id="report-task",
        name="Report Task",
        description="Generate a report.",
        acceptance_criteria=["Report exists."],
    )


def _verification() -> VerificationResult:
    return VerificationResult(
        status="failed",
        summary="Reportable failure.",
        unmet_criteria=["Report exists."],
    )


def test_report_generator_writes_markdown_and_json(tmp_path: Path) -> None:
    artifact = ReportGenerator(tmp_path).generate("run-1", _task(), [], _verification())

    assert artifact.path.name == "report.md"
    assert artifact.path.exists()
    assert (tmp_path / "run-1" / "report.json").exists()
    assert artifact.evidence_manifest_path is not None
    assert artifact.evidence_manifest_path.exists()


def test_report_generator_writes_minimal_json_fallback(tmp_path: Path) -> None:
    artifact = _FailingRichReportGenerator(tmp_path).generate("run-2", _task(), [], _verification())

    assert artifact.path.name == "report-fallback.json"
    assert artifact.format == "json"
    payload = json.loads(artifact.path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-2"
    assert payload["task_id"] == "report-task"
    assert payload["status"] == "failed"
    assert payload["summary"] == "Reportable failure."
    assert "simulated rich report failure" in payload["error"]