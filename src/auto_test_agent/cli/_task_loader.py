import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from auto_test_agent.models import ConfigurationError, Task


def load_task(path: str | Path) -> Task:
    task_path = Path(path)
    try:
        content = task_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError("Unable to read task file.", context={"path": str(task_path)}) from exc
    try:
        if task_path.suffix.lower() == ".json":
            data = json.loads(content)
        else:
            data = yaml.safe_load(content)
        return Task.model_validate(data)
    except (json.JSONDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise ConfigurationError("Invalid task file.", context={"path": str(task_path)}) from exc


def load_tasks(path: str | Path) -> list[Task]:
    task_path = Path(path)
    if task_path.is_file():
        return [load_task(task_path)]
    candidates = sorted(
        file_path
        for pattern in ("*.yaml", "*.yml", "*.json")
        for file_path in task_path.glob(pattern)
    )
    return [load_task(candidate) for candidate in candidates]