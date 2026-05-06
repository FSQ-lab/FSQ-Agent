import json
from pathlib import Path
from typing import Any

import yaml

from auto_test_agent.models import AutoTestAgentError, KnowledgeBundle, Task


class PrivateKnowledgeLoader:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir

    def load_for_task(self, task: Task) -> KnowledgeBundle:
        items: dict[str, Any] = {}
        warnings: list[str] = []
        for reference in task.knowledge_refs:
            path = (self.knowledge_dir / reference).resolve()
            if not path.exists():
                warnings.append(f"Knowledge reference not found: {reference}")
                continue
            try:
                items[reference] = self._load_path(path)
            except OSError as exc:
                raise AutoTestAgentError("Unable to load knowledge reference.", context={"path": str(path)}) from exc
        return KnowledgeBundle(items=items, warnings=warnings)

    def _load_path(self, path: Path) -> Any:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        return path.read_text(encoding="utf-8")