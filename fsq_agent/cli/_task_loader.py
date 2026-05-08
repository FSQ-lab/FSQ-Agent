from pathlib import Path

from fsq_agent.fsq import FsqCaseLoader, FsqTaskAdapter, is_fsq_case_file
from fsq_agent.models import ConfigurationError, Task


def _resolve_task_path(path: str | Path, cases_dir: Path | None = None) -> Path:
    task_path = Path(path).expanduser()
    if task_path.is_absolute():
        return task_path.resolve()
    if cases_dir is not None:
        candidate = (cases_dir / task_path).resolve()
        if candidate.exists():
            return candidate
    return task_path.resolve()


def load_task(path: str | Path, cases_dir: Path | None = None) -> Task:
    task_path = _resolve_task_path(path, cases_dir)
    if is_fsq_case_file(task_path):
        return FsqTaskAdapter().to_task(FsqCaseLoader().load_case(task_path))
    raise ConfigurationError("Task files must use the FSQ .codex.yaml format.", context={"path": str(task_path)})


def load_tasks(path: str | Path, cases_dir: Path | None = None) -> list[Task]:
    task_path = _resolve_task_path(path, cases_dir)
    if task_path.is_file():
        return [load_task(task_path, cases_dir)]
    return [load_task(candidate, cases_dir) for candidate in sorted(task_path.glob("**/*.codex.yaml"))]