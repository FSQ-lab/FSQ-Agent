import asyncio
import logging
from pathlib import Path
import re

import click

from fsq_agent.agent import FsqAgent
from fsq_agent.cli._formatting import log_capabilities, log_result, log_run_event
from fsq_agent.cli._logging import configure_cli_logging
from fsq_agent.cli._pre_plan_formatting import log_pre_plan
from fsq_agent.cli._task_loader import load_task, load_tasks
from fsq_agent.config import load_settings, validate_runtime_settings
from fsq_agent.models import FsqAgentError, Task, VerificationCriterion
from fsq_agent.tools import CapabilityRegistry


logger = logging.getLogger(__name__)


@click.group()
def main() -> None:
    configure_cli_logging()


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
def init(config_path: str | None, workspace_path: str | None) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        logger.info("Initialized fsq-agent workspace: %s", settings.workspace.root_dir)
        logger.info("Output root: %s", settings.output.root_dir)
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        raise click.Abort() from exc


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--task", "task_path", type=click.Path(exists=False, dir_okay=False), required=True)
@click.option("--stream/--no-stream", "stream", default=True, show_default=True)
@click.option("--stream-format", type=click.Choice(["rich", "jsonl"]), default="rich", show_default=True)
def run(config_path: str | None, workspace_path: str | None, task_path: str, stream: bool, stream_format: str) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        task = load_task(task_path, settings.cases.dir)
        sink = (lambda event: log_run_event(event, stream_format)) if stream else None
        result = asyncio.run(FsqAgent.from_settings(settings).run(task, event_sink=sink))
        log_result(result)
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        raise click.Abort() from exc


@main.command("run-goal")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--goal", required=True)
@click.option("--stream/--no-stream", "stream", default=True, show_default=True)
@click.option("--stream-format", type=click.Choice(["rich", "jsonl"]), default="rich", show_default=True)
def run_goal(config_path: str | None, workspace_path: str | None, goal: str, stream: bool, stream_format: str) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        task = _task_from_goal(goal)
        sink = (lambda event: log_run_event(event, stream_format)) if stream else None
        result = asyncio.run(FsqAgent.from_settings(settings).run(task, event_sink=sink))
        log_result(result)
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        raise click.Abort() from exc


@main.command("run-batch")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--tasks", "tasks_path", type=click.Path(exists=False), default=None)
@click.option("--stream/--no-stream", "stream", default=True, show_default=True)
@click.option("--stream-format", type=click.Choice(["rich", "jsonl"]), default="rich", show_default=True)
def run_batch(
    config_path: str | None,
    workspace_path: str | None,
    tasks_path: str | None,
    stream: bool,
    stream_format: str,
) -> None:
    async def _run_all() -> None:
        settings = load_settings(config_path, workspace_path)
        task_root = tasks_path or settings.cases.dir

        results = []
        for task in load_tasks(task_root, settings.cases.dir):
            sink = (lambda event: log_run_event(event, stream_format)) if stream else None
            results.append(await FsqAgent.from_settings(settings).run(task, event_sink=sink))
        for result in results:
            log_result(result)

    try:
        asyncio.run(_run_all())
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        raise click.Abort() from exc


@main.command("pre-plan")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--goal", required=True)
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option("--stream/--no-stream", "stream", default=True, show_default=True)
@click.option("--stream-format", type=click.Choice(["rich", "jsonl"]), default="rich", show_default=True)
def pre_plan(
    config_path: str | None,
    workspace_path: str | None,
    goal: str,
    output_format: str,
    stream: bool,
    stream_format: str,
) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        sink = (lambda event: log_run_event(event, stream_format)) if stream else None
        plan = asyncio.run(FsqAgent.from_settings(settings).pre_plan_goal(goal, event_sink=sink))
        log_pre_plan(plan, output_format)
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        if exc.context:
            logger.error("Details: %s", exc.context)
        raise click.Abort() from exc


@main.command("validate-config")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
def validate_config(config_path: str | None, workspace_path: str | None) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        validate_runtime_settings(settings)
        logger.info("Configuration valid. OpenAI Agents SDK enabled: %s", settings.openai_agents.enabled)
        logger.info("Model: %s", settings.openai_agents.model)
        logger.info("Base URL: %s", settings.openai_agents.base_url)
        logger.info("API key env: %s", settings.openai_agents.api_key_env)
        logger.info("Workspace: %s", settings.workspace.root_dir)
        logger.info("Cases: %s", settings.cases.dir)
        logger.info("Output: %s", settings.output.root_dir)
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        raise click.Abort() from exc


@main.command()
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
def capabilities(config_path: str | None, workspace_path: str | None) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        log_capabilities(CapabilityRegistry.from_cli_tools(settings.cli_tools).list_tools())
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
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
        logger.error("Report not found: %s", path)
        raise click.Abort()
    logger.info(path.read_text(encoding="utf-8"))


def _task_from_goal(goal: str) -> Task:
    normalized_goal = " ".join(goal.split())
    task_id = _goal_task_id(normalized_goal)
    verification_goal = f"Goal completed: {normalized_goal}"
    return Task(
        id=task_id,
        name=normalized_goal,
        description=(
            "Run this natural-language goal as a goal-driven automation task. "
            "First derive ordered key actions from page knowledge, then execute them while adapting to live UI state. "
            "Final verification should judge whether the goal is complete.\n\n"
            f"Goal: {normalized_goal}"
        ),
        acceptance_criteria=[verification_goal],
        verification_goal=verification_goal,
        verification_criteria=[VerificationCriterion(text=verification_goal, kind="goal", source="cli_goal")],
    )


def _goal_task_id(goal: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", goal.casefold()).strip("-")
    return slug[:80] or "goal-task"