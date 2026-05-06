from rich.console import Console
from rich.table import Table

from auto_test_agent.models import TaskResult, ToolDefinition


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