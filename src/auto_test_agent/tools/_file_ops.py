import time
from pathlib import Path
from typing import Any

from auto_test_agent.models import ToolExecutionError, ToolResult


class FileOps:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path.cwd()).resolve()

    def _resolve_scoped(self, path_value: object) -> Path:
        if not isinstance(path_value, str):
            raise ToolExecutionError("File path must be a string.")
        path = (self.root / path_value).resolve()
        if self.root not in (path, *path.parents):
            raise ToolExecutionError("File path is outside the allowed root.", context={"path": str(path)})
        return path

    async def read_text(self, arguments: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        path = self._resolve_scoped(arguments.get("path"))
        try:
            content = path.read_text(encoding=str(arguments.get("encoding", "utf-8")))
        except OSError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return ToolResult(tool_name="file.read", status="failed", error=str(exc), duration_ms=duration_ms)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return ToolResult(tool_name="file.read", status="success", output=content, duration_ms=duration_ms)

    async def write_text(self, arguments: dict[str, Any]) -> ToolResult:
        started = time.perf_counter()
        path = self._resolve_scoped(arguments.get("path"))
        content = arguments.get("content", "")
        if not isinstance(content, str):
            raise ToolExecutionError("File content must be a string.")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding=str(arguments.get("encoding", "utf-8")))
        except OSError as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            return ToolResult(tool_name="file.write", status="failed", error=str(exc), duration_ms=duration_ms)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return ToolResult(tool_name="file.write", status="success", output=str(path), duration_ms=duration_ms)