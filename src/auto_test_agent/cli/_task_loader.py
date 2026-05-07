from pathlib import Path

from auto_test_agent.fsq import FsqCaseLoader, FsqTaskAdapter, is_fsq_case_file
from auto_test_agent.models import ConfigurationError, Task


def load_task(path: str | Path) -> Task:
    task_path = Path(path)
    if is_fsq_case_file(task_path):
        return FsqTaskAdapter().to_task(FsqCaseLoader().load_case(task_path))
    raise ConfigurationError("Task files must use the FSQ .codex.yaml format.", context={"path": str(task_path)})


def load_tasks(path: str | Path) -> list[Task]:
    task_path = Path(path)
    if task_path.is_file():
        return [load_task(task_path)]
    return [load_task(candidate) for candidate in sorted(task_path.glob("**/*.codex.yaml"))]