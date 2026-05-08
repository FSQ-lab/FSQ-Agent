import asyncio
from pathlib import Path

import click

from fsq_agent.agent import FsqAgent
from fsq_agent.cli._formatting import console, print_capabilities, print_result
from fsq_agent.cli._task_loader import load_task, load_tasks
from fsq_agent.config import load_settings, validate_runtime_settings
from fsq_agent.models import FsqAgentError
from fsq_agent.tools import CapabilityRegistry


@click.group()
def main() -> None:
    pass


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
def init(config_path: str | None, workspace_path: str | None) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        console.print(f"Initialized fsq-agent workspace: {settings.workspace.root_dir}")
        console.print(f"Output root: {settings.output.root_dir}")
    except FsqAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--task", "task_path", type=click.Path(exists=False, dir_okay=False), required=True)
def run(config_path: str | None, workspace_path: str | None, task_path: str) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        task = load_task(task_path, settings.cases.dir)
        result = asyncio.run(FsqAgent.from_settings(settings).run(task))
        print_result(result)
    except FsqAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command("run-batch")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--tasks", "tasks_path", type=click.Path(exists=False), default=None)
@click.option("--parallel", "parallelism", type=int, default=1, show_default=True)
def run_batch(config_path: str | None, workspace_path: str | None, tasks_path: str | None, parallelism: int) -> None:
    async def _run_all() -> None:
        settings = load_settings(config_path, workspace_path)
        task_root = tasks_path or settings.cases.dir
        semaphore = asyncio.Semaphore(max(1, parallelism))

        async def _run_one(task_path_task):
            async with semaphore:
                return await FsqAgent.from_settings(settings).run(task_path_task)

        results = await asyncio.gather(*[_run_one(task) for task in load_tasks(task_root, settings.cases.dir)])
        for result in results:
            print_result(result)

    try:
        asyncio.run(_run_all())
    except FsqAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command("validate-config")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
def validate_config(config_path: str | None, workspace_path: str | None) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        validate_runtime_settings(settings)
        console.print(f"Configuration valid. OpenAI Agents SDK enabled: {settings.openai_agents.enabled}")
        console.print(f"Model: {settings.openai_agents.model}")
        console.print(f"Base URL: {settings.openai_agents.base_url}")
        console.print(f"API key env: {settings.openai_agents.api_key_env}")
        console.print(f"Workspace: {settings.workspace.root_dir}")
        console.print(f"Cases: {settings.cases.dir}")
        console.print(f"Output: {settings.output.root_dir}")
    except FsqAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
def capabilities(config_path: str | None, workspace_path: str | None) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        print_capabilities(CapabilityRegistry.from_cli_tools(settings.cli_tools).list_tools())
    except FsqAgentError as exc:
        console.print(f"Error: {exc}")
        raise click.Abort() from exc


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--run-id", required=True)
@click.option("--format", "report_format", type=click.Choice(["markdown", "json"]), default="markdown")
def report(config_path: str | None, workspace_path: str | None, run_id: str, report_format: str) -> None:
    suffix = "md" if report_format == "markdown" else "json"
    settings = load_settings(config_path, workspace_path)
    path = Path(settings.output.runs_dir) / run_id / f"report.{suffix}"
    if not path.exists():
        console.print(f"Report not found: {path}")
        raise click.Abort()
    console.print(path.read_text(encoding="utf-8"))