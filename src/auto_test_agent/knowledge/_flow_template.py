from pathlib import Path
from typing import Any

import yaml


class FlowTemplateManager:
    def __init__(self, flows_dir: Path) -> None:
        self.flows_dir = flows_dir

    def load_templates(self) -> dict[str, Any]:
        if not self.flows_dir.exists():
            return {}
        templates: dict[str, Any] = {}
        for path in sorted(self.flows_dir.glob("*.y*ml")):
            templates[path.stem] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return templates

    def match(self, task_description: str) -> dict[str, Any]:
        normalized = task_description.lower()
        return {
            name: template
            for name, template in self.load_templates().items()
            if name.lower().replace("-", " ") in normalized
        }