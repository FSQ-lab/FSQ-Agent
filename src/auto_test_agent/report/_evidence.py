import json
from pathlib import Path

from auto_test_agent.models import StepResult


class EvidenceBundler:
    def __init__(self, reports_dir: Path) -> None:
        self.reports_dir = reports_dir

    def create_manifest(self, run_id: str, steps: list[StepResult]) -> Path:
        path = self.reports_dir / run_id / "evidence-manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "run_id": run_id,
            "steps": [
                {
                    "step_id": step.step_id,
                    "status": step.status,
                    "screenshot_path": str(step.screenshot_path) if step.screenshot_path else None,
                    "has_ui_tree": step.ui_tree_snapshot is not None,
                }
                for step in steps
            ],
        }
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return path