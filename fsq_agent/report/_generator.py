import json
from pathlib import Path

from fsq_agent.models import ReportArtifact, ReportGenerationError, StepResult, Task, VerificationResult
from fsq_agent.report._evidence import EvidenceBundler
from fsq_agent.report._failure_analysis import FailureAnalyzer


class ReportGenerator:
    def __init__(self, reports_dir: Path, evidence_bundler: EvidenceBundler | None = None) -> None:
        self.reports_dir = reports_dir
        self.evidence_bundler = evidence_bundler or EvidenceBundler(reports_dir)
        self.failure_analyzer = FailureAnalyzer()

    def generate(
        self,
        run_id: str,
        task: Task,
        steps: list[StepResult],
        verification: VerificationResult,
    ) -> ReportArtifact:
        report_dir = self.reports_dir / run_id
        report_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.evidence_bundler.create_manifest(run_id, steps)
        report_path = report_dir / "report.md"
        try:
            self._write_rich_reports(report_dir, report_path, task, steps, verification)
        except OSError as exc:
            return self._write_minimal_fallback(run_id, report_dir, task, verification, manifest_path, exc)
        return ReportArtifact(run_id=run_id, path=report_path, evidence_manifest_path=manifest_path)

    def _write_rich_reports(
        self,
        report_dir: Path,
        report_path: Path,
        task: Task,
        steps: list[StepResult],
        verification: VerificationResult,
    ) -> None:
        report_path.write_text(
            self._render_markdown(task, steps, verification),
            encoding="utf-8",
        )
        json_path = report_dir / "report.json"
        json_path.write_text(
            json.dumps(
                {
                    "task": task.model_dump(mode="json"),
                    "steps": [step.model_dump(mode="json") for step in steps],
                    "verification": verification.model_dump(mode="json"),
                    "failure_classification": self.failure_analyzer.classify(steps, verification),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def _write_minimal_fallback(
        self,
        run_id: str,
        report_dir: Path,
        task: Task,
        verification: VerificationResult,
        manifest_path: Path,
        error: OSError,
    ) -> ReportArtifact:
        fallback_path = report_dir / "report-fallback.json"
        try:
            fallback_path.write_text(
                json.dumps(
                    {
                        "run_id": run_id,
                        "task_id": task.id,
                        "status": verification.status,
                        "summary": verification.summary,
                        "error": str(error),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError as fallback_error:
            raise ReportGenerationError("Unable to generate report.", context={"run_id": run_id}) from fallback_error
        return ReportArtifact(
            run_id=run_id,
            path=fallback_path,
            format="json",
            evidence_manifest_path=manifest_path,
        )

    def _render_markdown(self, task: Task, steps: list[StepResult], verification: VerificationResult) -> str:
        lines = [
            f"# Test Report: {task.name}",
            "",
            f"Task ID: `{task.id}`",
            f"Status: `{verification.status}`",
            "",
            "## Summary",
            "",
            verification.summary,
            "",
            "## Steps",
            "",
        ]
        for step in steps:
            lines.extend(
                [
                    f"### Step {step.step_id}: {step.status}",
                    "",
                    step.actual_outcome,
                    "",
                ]
            )
            if step.error:
                lines.extend([f"Error: `{step.error}`", ""])
        if verification.unmet_criteria:
            lines.extend(["## Unmet Criteria", ""])
            lines.extend(f"- {criterion}" for criterion in verification.unmet_criteria)
            lines.append("")
        if verification.satisfied_criteria:
            lines.extend(["## Satisfied Criteria", ""])
            lines.extend(f"- {criterion}" for criterion in verification.satisfied_criteria)
            lines.append("")
        if verification.diagnostics:
            lines.extend(["## Diagnostics", ""])
            lines.extend(f"- {diagnostic}" for diagnostic in verification.diagnostics)
            lines.append("")
        return "\n".join(lines)