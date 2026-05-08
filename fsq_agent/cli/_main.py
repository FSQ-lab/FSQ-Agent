import asyncio
from pathlib import Path

import click

from fsq_agent.agent import AutoTestAgent
from fsq_agent.cli._formatting import console, print_capabilities, print_result
from fsq_agent.cli._task_loader import load_task, load_tasks
from fsq_agent.config import load_settings, validate_runtime_settings
from fsq_agent.models import AutoTestAgentError
from fsq_agent.tools import CapabilityRegistry


@click.group()
def main() -> None:
    pass


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--task", "task_path", type=click.Path(exists=True, dir_okay=False), required=True)
def run(config_path: str | None, task_path: str) -> None:
    try:
        task = load_task(task_path)
        result = asyncio.run(AutoTestAgent.from_config(config_path).run(task))
        print_result(result)
    except AutoTestAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command("run-batch")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--tasks", "tasks_path", type=click.Path(exists=True), required=True)
@click.option("--parallel", "parallelism", type=int, default=1, show_default=True)
def run_batch(config_path: str | None, tasks_path: str, parallelism: int) -> None:
    async def _run_all() -> None:
        semaphore = asyncio.Semaphore(max(1, parallelism))

        async def _run_one(task_path_task):
            async with semaphore:
                return await AutoTestAgent.from_config(config_path).run(task_path_task)

        results = await asyncio.gather(*[_run_one(task) for task in load_tasks(tasks_path)])
        for result in results:
            print_result(result)

    try:
        asyncio.run(_run_all())
    except AutoTestAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command("validate-config")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
def validate_config(config_path: str | None) -> None:
    try:
        settings = load_settings(config_path)
        validate_runtime_settings(settings)
        console.print(f"Configuration valid. OpenAI Agents SDK enabled: {settings.openai_agents.enabled}")
        console.print(f"Model: {settings.openai_agents.model}")
        console.print(f"Base URL: {settings.openai_agents.base_url}")
        console.print(f"API key env: {settings.openai_agents.api_key_env}")
    except AutoTestAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
def capabilities(config_path: str | None) -> None:
    try:
        settings = load_settings(config_path)
        print_capabilities(CapabilityRegistry.from_cli_tools(settings.cli_tools).list_tools())
    except AutoTestAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command()
@click.option("--run-id", required=True)
@click.option("--format", "report_format", type=click.Choice(["markdown", "json"]), default="markdown")
@click.option("--reports-dir", type=click.Path(file_okay=False), default="reports")
def report(run_id: str, report_format: str, reports_dir: str) -> None:
    suffix = "md" if report_format == "markdown" else "json"
    path = Path(reports_dir) / run_id / f"report.{suffix}"
    if not path.exists():
        console.print(f"Report not found: {path}")
        raise click.Abort()
    console.print(path.read_text(encoding="utf-8"))