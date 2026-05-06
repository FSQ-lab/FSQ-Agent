from pathlib import Path

from auto_test_agent.config._settings import Settings


def _resolve_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def resolve_output_dirs(settings: Settings) -> None:
    settings.output.logs_dir = _resolve_dir(settings.output.logs_dir)
    settings.output.reports_dir = _resolve_dir(settings.output.reports_dir)
    settings.output.screenshots_dir = _resolve_dir(settings.output.screenshots_dir)
    settings.output.traces_dir = _resolve_dir(settings.output.traces_dir)
    settings.knowledge_dir = settings.knowledge_dir.expanduser().resolve()
    settings.shell.working_dir = settings.shell.working_dir.expanduser().resolve()