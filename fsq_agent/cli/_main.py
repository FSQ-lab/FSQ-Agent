import asyncio
import json
import logging
from pathlib import Path
import re
import time

import click

from fsq_agent.agent import FsqAgent, OpenAIAssertionEvaluator
from fsq_agent.cli._formatting import log_capabilities, log_result, log_run_event
from fsq_agent.cli._core_execution import run_strict_fsq_core_case
from fsq_agent.cli._logging import configure_cli_logging
from fsq_agent.cli._pre_plan_formatting import log_pre_plan
from fsq_agent.cli._task_loader import _resolve_task_path, load_task, load_tasks
from fsq_agent.config import load_settings, validate_runtime_settings
from fsq_agent.core import AndroidHarness, ArtifactStore, UiAutomator2AndroidDriver
from fsq_agent.fsq import FsqCaseLoader
from fsq_agent.models import ConfigurationError, FsqAgentError, Task, VerificationCriterion
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


@main.command("run-strict-core")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--task", "task_path", type=click.Path(exists=False, dir_okay=False), required=True)
@click.option("--android-serial", required=True)
@click.option("--app-id", default=None)
@click.option("--run-id", default=None)
@click.option("--enable-ai-assertions", is_flag=True, default=False, show_default=True)
def run_strict_core(
    config_path: str | None,
    workspace_path: str | None,
    task_path: str,
    android_serial: str,
    app_id: str | None,
    run_id: str | None,
    enable_ai_assertions: bool,
) -> None:
    try:
        settings = load_settings(config_path, workspace_path)
        resolved_task_path = _resolve_task_path(task_path, settings.cases.dir)
        case = FsqCaseLoader().load_case(resolved_task_path)
        resolved_app_id = app_id or case.config.app_id
        if not resolved_app_id:
            raise ConfigurationError(
                "Android app id is required for strict core runs.",
                context={"task": str(resolved_task_path)},
            )
        resolved_run_id = run_id or case.id
        run_dir = Path(settings.output.runs_dir) / resolved_run_id
        driver = UiAutomator2AndroidDriver(app_id=resolved_app_id, serial=android_serial)
        ai_assertion_evaluator = None
        if enable_ai_assertions:
            validate_runtime_settings(settings)
            ai_assertion_evaluator = OpenAIAssertionEvaluator(settings)
        harness = AndroidHarness(
            driver=driver,
            artifact_store=ArtifactStore(run_dir=run_dir),
            ai_assertion_evaluator=ai_assertion_evaluator,
        )
        artifact = run_strict_fsq_core_case(
            case_path=resolved_task_path,
            harness=harness,
            output_dir=run_dir,
            run_id=resolved_run_id,
        )
        logger.info("Core report: %s", artifact.path)
        logger.info("Evidence manifest: %s", artifact.evidence_manifest_path)
    except FsqAgentError as exc:
        logger.error("Error: %s", exc)
        raise click.Abort() from exc


@main.command("run-strict-core-batch")
@click.option("--config", "config_path", type=click.Path(exists=False, dir_okay=False), default=None)
@click.option("--workspace", "workspace_path", type=click.Path(file_okay=False), default=None)
@click.option("--tasks", "tasks_path", type=click.Path(exists=False), default=None)
@click.option("--android-serial", required=True)
@click.option("--app-id", default=None)
@click.option("--run-prefix", default=None)
@click.option("--enable-ai-assertions", is_flag=True, default=False, show_default=True)
def run_strict_core_batch(
    config_path: str | None,
    workspace_path: str | None,
    tasks_path: str | None,
    android_serial: str,
    app_id: str | None,
    run_prefix: str | None,
    enable_ai_assertions: bool,
) -> None:
    settings = load_settings(config_path, workspace_path)
    task_root = Path(tasks_path) if tasks_path else Path(settings.cases.dir)
    case_paths = sorted(task_root.rglob("*.codex.yaml")) if task_root.is_dir() else [task_root]
    batch_id = run_prefix or f"strict-core-batch-{time.strftime('%Y-%m-%d_%H-%M-%S')}"
    batch_dir = Path(settings.output.runs_dir) / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    ai_assertion_evaluator = None
    if enable_ai_assertions:
        validate_runtime_settings(settings)
        ai_assertion_evaluator = OpenAIAssertionEvaluator(settings)

    cases: list[dict[str, object]] = []
    for index, case_path in enumerate(case_paths, start=1):
        resolved_case_path = _resolve_task_path(str(case_path), settings.cases.dir)
        run_id = f"{batch_id}-{_case_run_slug(resolved_case_path, index)}"
        run_dir = Path(settings.output.runs_dir) / run_id
        try:
            case = FsqCaseLoader().load_case(resolved_case_path)
            resolved_app_id = app_id or case.config.app_id
            if not resolved_app_id:
                raise ConfigurationError(
                    "Android app id is required for strict core batch runs.",
                    context={"task": str(resolved_case_path)},
                )
            driver = UiAutomator2AndroidDriver(app_id=resolved_app_id, serial=android_serial)
            harness = AndroidHarness(
                driver=driver,
                artifact_store=ArtifactStore(run_dir=run_dir),
                ai_assertion_evaluator=ai_assertion_evaluator,
            )
            artifact = run_strict_fsq_core_case(
                case_path=resolved_case_path,
                harness=harness,
                output_dir=run_dir,
                run_id=run_id,
            )
            cases.append(
                {
                    "case_path": str(resolved_case_path),
                    "run_id": run_id,
                    "status": "passed",
                    "report_path": str(artifact.path),
                    "evidence_manifest_path": str(artifact.evidence_manifest_path),
                    "error": None,
                }
            )
            logger.info("Strict core case passed: %s", resolved_case_path)
        except Exception as exc:
            cases.append(
                {
                    "case_path": str(resolved_case_path),
                    "run_id": run_id,
                    "status": "failed",
                    "report_path": None,
                    "evidence_manifest_path": None,
                    "error": str(exc),
                }
            )
            logger.error("Strict core case failed: %s: %s", resolved_case_path, exc)

    summary = _strict_core_batch_summary(batch_id, batch_dir, cases)
    summary_json_path = batch_dir / "strict-core-batch-summary.json"
    summary_md_path = batch_dir / "strict-core-batch-summary.md"
    summary_json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    summary_md_path.write_text(_strict_core_batch_markdown(summary), encoding="utf-8")
    logger.info("Strict core batch summary: %s", summary_json_path)
    logger.info("Strict core batch report: %s", summary_md_path)
    if summary["failed"]:
        raise click.exceptions.Exit(1)


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
        logger.info("Configuration valid. OpenAI Agents SDK provider: %s", settings.openai_agents.provider)
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


def _case_run_slug(case_path: Path, index: int) -> str:
    stem = case_path.name.removesuffix(".codex.yaml")
    slug = re.sub(r"[^a-z0-9]+", "-", stem.casefold()).strip("-")
    return f"{index:03d}-{slug[:80] or 'case'}"


def _strict_core_batch_summary(batch_id: str, batch_dir: Path, cases: list[dict[str, object]]) -> dict[str, object]:
    passed = sum(1 for case in cases if case["status"] == "passed")
    failed = sum(1 for case in cases if case["status"] == "failed")
    return {
        "batch_id": batch_id,
        "batch_dir": str(batch_dir),
        "total": len(cases),
        "passed": passed,
        "failed": failed,
        "cases": cases,
    }


def _strict_core_batch_markdown(summary: dict[str, object]) -> str:
    lines = [
        f"# Strict Core Batch: {summary['batch_id']}",
        "",
        f"Total: `{summary['total']}`",
        f"Passed: `{summary['passed']}`",
        f"Failed: `{summary['failed']}`",
        "",
        "| Status | Case | Run | Error |",
        "|---|---|---|---|",
    ]
    for case in summary["cases"]:
        if not isinstance(case, dict):
            continue
        lines.append(
            "| {status} | {case_path} | {run_id} | {error} |".format(
                status=case.get("status", ""),
                case_path=case.get("case_path", ""),
                run_id=case.get("run_id", ""),
                error=str(case.get("error") or "").replace("|", "\\|"),
            )
        )
    return "\n".join(lines) + "\n"
