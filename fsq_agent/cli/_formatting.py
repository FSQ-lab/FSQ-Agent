import json

from rich.console import Console
from rich.table import Table

from fsq_agent.models import RunEvent, TaskResult, ToolDefinition


console = Console()


def print_capabilities(capabilities: list[ToolDefinition]) -> None:
    table = Table(title="Available Capabilities")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Description")
    for capability in capabilities:
        table.add_row(capability.name, capability.kind, capability.description)
    console.print(table)


def print_result(result: TaskResult) -> None:
    console.print(f"Task {result.task_id}: {result.status}")
    console.print(f"Report: {result.report.path}")


def print_run_event(event: RunEvent, stream_format: str = "rich") -> None:
    if stream_format == "jsonl":
        console.print(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))
        return

    prefix = f"[{event.sequence}] {event.title}"
    if event.type in {"tool_call_started", "tool_call_completed", "tool_call_failed"} and event.tool_name:
        prefix = f"{prefix}: {event.tool_name}"
    style = _event_style(event.type)
    console.print(f"{prefix}", style=style)
    if event.message:
        console.print(f"  {event.message}")
    if event.tool_arguments is not None:
        console.print(f"  args: {_compact(event.tool_arguments)}")
    if event.tool_output_preview:
        console.print(f"  output: {event.tool_output_preview}")
    if event.duration_ms is not None:
        console.print(f"  duration: {event.duration_ms}ms")


def _event_style(event_type: str) -> str:
    if event_type.endswith("failed") or event_type == "run_failed":
        return "bold red"
    if event_type.endswith("completed") or event_type == "run_completed":
        return "green"
    if event_type.startswith("tool_call"):
        return "cyan"
    if event_type in {"planning_started", "planning_update", "reasoning_summary"}:
        return "magenta"
    return "bold"


def _compact(value: object, limit: int = 1000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    text = text.replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}..."
