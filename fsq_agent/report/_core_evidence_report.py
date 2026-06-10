import json
from pathlib import Path
from typing import Any

from fsq_agent.models import EvidenceBundle, ReportArtifact


class CoreEvidenceReportGenerator:
    def generate_from_manifest(self, manifest_path: Path) -> ReportArtifact:
        bundle = self._load_bundle(manifest_path)
        report_dir = manifest_path.parent
        markdown_path = report_dir / "core-report.md"
        json_path = report_dir / "core-report.json"
        report = self._build_report(bundle, manifest_path)
        markdown_path.write_text(self._render_markdown(report), encoding="utf-8")
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return ReportArtifact(
            run_id=bundle.run_id,
            path=markdown_path,
            evidence_manifest_path=manifest_path,
        )

    def _load_bundle(self, manifest_path: Path) -> EvidenceBundle:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return EvidenceBundle.model_validate(payload).model_copy(update={"manifest_path": manifest_path})

    def _build_report(self, bundle: EvidenceBundle, manifest_path: Path) -> dict[str, Any]:
        failed_steps = [step for step in bundle.steps if step.status != "passed"]
        return {
            "run_id": bundle.run_id,
            "bundle_id": bundle.bundle_id,
            "manifest_path": str(manifest_path),
            "metadata": bundle.metadata,
            "summary": {
                "status": "failed" if failed_steps else "passed",
                "step_count": len(bundle.steps),
                "passed_steps": len([step for step in bundle.steps if step.status == "passed"]),
                "failed_steps": len(failed_steps),
                "artifact_count": len(bundle.artifacts),
            },
            "steps": [step.model_dump(mode="json") for step in bundle.steps],
            "events": [event.model_dump(mode="json") for event in bundle.events],
            "artifacts": [artifact.model_dump(mode="json") for artifact in bundle.artifacts],
        }

    def _render_markdown(self, report: dict[str, Any]) -> str:
        summary = report["summary"]
        lines = [
            f"# Core Evidence Report: {report['run_id']}",
            "",
            f"Status: `{summary['status']}`",
            f"Manifest: `{report['manifest_path']}`",
            "",
            "## Summary",
            "",
            f"- Steps: `{summary['step_count']}`",
            f"- Passed steps: `{summary['passed_steps']}`",
            f"- Failed steps: `{summary['failed_steps']}`",
            f"- Artifacts: `{summary['artifact_count']}`",
            "",
            "## Steps",
            "",
            "| Step | Status | Failure Category | Error |",
            "|---|---:|---|---|",
        ]
        for step in report["steps"]:
            lines.append(
                f"| `{step['step_id']}` | `{step['status']}` | "
                f"`{step.get('failure_category') or ''}` | {step.get('error_message') or ''} |"
            )

        failed_steps = [step for step in report["steps"] if step["status"] != "passed"]
        if failed_steps:
            lines.extend(["", "## Failures", ""])
            for step in failed_steps:
                lines.append(
                    f"- `{step['step_id']}` failed with `{step.get('failure_category') or 'unknown'}`: "
                    f"{step.get('error_message') or 'No error message.'}"
                )

        lines.extend(["", "## Events", ""])
        for event in report["events"]:
            phase = f"/{event['phase']}" if event.get("phase") else ""
            step_id = event.get("step_id") or "run"
            lines.append(f"- `{event['event_type']}` `{step_id}{phase}`")

        lines.extend(["", "## Artifacts", ""])
        if report["artifacts"]:
            for artifact in report["artifacts"]:
                lines.append(f"- `{artifact['kind']}` `{artifact['path']}`")
        else:
            lines.append("No artifacts recorded.")
        lines.append("")
        return "\n".join(lines)
