import json
from pathlib import Path
from typing import Any

from fsq_agent.models import ReportArtifact, ReportGenerationError, StepResult, Task, VerificationResult
from fsq_agent.report._evidence import EvidenceBundler
from fsq_agent.report._failure_analysis import FailureAnalyzer


class ReportGenerator:
    def __init__(self, runs_dir: Path, evidence_bundler: EvidenceBundler | None = None) -> None:
        self.runs_dir = runs_dir
        self.evidence_bundler = evidence_bundler or EvidenceBundler(runs_dir)
        self.failure_analyzer = FailureAnalyzer()

    def generate(
        self,
        run_id: str,
        task: Task,
        steps: list[StepResult],
        verification: VerificationResult,
    ) -> ReportArtifact:
        report_dir = self.runs_dir / run_id
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
            json.dumps(self._build_json_report(report_dir, task, steps, verification), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _build_json_report(
        self,
        report_dir: Path,
        task: Task,
        steps: list[StepResult],
        verification: VerificationResult,
    ) -> dict[str, Any]:
        final_output = self._parse_runner_output(steps)
        return {
            "task": task.model_dump(mode="json"),
            "plan": {
                "source": "openai_agents.runner.final_output" if final_output else "unavailable",
                "items": final_output.get("pre_plan", []) if final_output else [],
                "updates": final_output.get("plan_updates", []) if final_output else [],
            },
            "execution": {
                "step_records": [self._step_record(step) for step in steps],
                "tool_calls": self._load_tool_calls(report_dir),
            },
            "verification": verification.model_dump(mode="json"),
            "failure_classification": self.failure_analyzer.classify(steps, verification),
        }

    def _parse_runner_output(self, steps: list[StepResult]) -> dict[str, Any] | None:
        runner_steps = [step for step in steps if step.tool_name == "openai_agents.runner"]
        if not runner_steps:
            return None
        try:
            payload = json.loads(runner_steps[-1].actual_outcome)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def _step_record(self, step: StepResult) -> dict[str, Any]:
        return {
            "step_id": step.step_id,
            "status": step.status,
            "source": step.tool_name or "runtime",
            "outcome": step.actual_outcome,
            "error": step.error,
            "duration_ms": step.duration_ms,
            "screenshot_path": str(step.screenshot_path) if step.screenshot_path else None,
            "tool_output": step.tool_output,
        }

    def _load_tool_calls(self, report_dir: Path) -> list[dict[str, Any]]:
        events_path = report_dir / "events.jsonl"
        if not events_path.exists():
            return []

        starts: dict[str, dict[str, Any]] = {}
        calls: list[dict[str, Any]] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            call_id = str(event.get("tool_call_id") or "")
            if event_type == "tool_call_started" and call_id:
                starts[call_id] = event
                continue
            if event_type not in {"tool_call_completed", "tool_call_failed"}:
                continue

            start = starts.get(call_id, {}) if call_id else {}
            calls.append(
                {
                    "tool_call_id": call_id or None,
                    "tool_name": start.get("tool_name") or event.get("tool_name"),
                    "status": "failed" if event_type == "tool_call_failed" else "completed",
                    "started_sequence": start.get("sequence"),
                    "completed_sequence": event.get("sequence"),
                    "started_at": start.get("timestamp"),
                    "completed_at": event.get("timestamp"),
                    "arguments": start.get("tool_arguments"),
                    "output_preview": event.get("tool_output_preview"),
                    "duration_ms": event.get("duration_ms"),
                }
            )
        return calls

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
        final_output = self._parse_runner_output(steps)
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
            "## Plan",
            "",
        ]
        if final_output and final_output.get("pre_plan"):
            for item in final_output["pre_plan"]:
                lines.extend(
                    [
                        f"### Plan Item {item.get('step_id', '?')}: {item.get('status', 'unknown')}",
                        "",
                        str(item.get("action", "")),
                        "",
                    ]
                )
                criteria = item.get("success_criteria") or []
                if criteria:
                    lines.extend(f"- {criterion}" for criterion in criteria)
                    lines.append("")
        else:
            lines.extend(["No plan was available in the runner final output.", ""])
        if final_output and final_output.get("plan_updates"):
            lines.extend(["## Plan Updates", ""])
            lines.extend(f"- {update}" for update in final_output["plan_updates"])
            lines.append("")

        lines.extend(["## Execution Records", ""])
        for step in steps:
            lines.extend(
                [
                    f"### Step {step.step_id}: {step.status} ({step.tool_name or 'runtime'})",
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