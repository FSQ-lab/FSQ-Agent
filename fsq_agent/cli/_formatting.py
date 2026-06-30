import json
import logging
from typing import Any

from fsq_agent.models import RunEvent, TaskResult


logger = logging.getLogger(__name__)


def log_result(result: TaskResult) -> None:
    logger.info("Task %s: %s", result.task_id, result.status)
    logger.info("Report: %s", result.report.path)


def log_run_event(event: RunEvent, stream_format: str = "rich") -> None:
    if stream_format == "jsonl":
        logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=False), extra={"fsq_raw_message": True})
        return

    _event_logger(event)(_format_rich_event(event))


def _event_logger(event: RunEvent):
    if event.type in {"tool_call_failed", "run_failed"} or _tool_status(event) == "failed":
        return logger.error
    return logger.info


def _format_rich_event(event: RunEvent) -> str:
    if event.type in {"tool_call_started", "tool_call_completed", "tool_call_failed"}:
        return _format_tool_event(event)
    if event.type == "reasoning_summary":
        return f"[{_event_phase(event)} #{event.sequence}] model reason: {_compact(event.message, limit=420)}"

    status = _event_status(event)
    line = f"[{_event_phase(event)} #{event.sequence}] {status}: {event.title}"
    if event.message:
        line = f"{line} - {_compact(event.message, limit=420)}"
    if event.duration_ms is not None:
        line = f"{line} duration={event.duration_ms}ms"
    output_hint = _output_hint(event.payload)
    if output_hint:
        line = f"{line} {output_hint}"
    return line


def _format_tool_event(event: RunEvent) -> str:
    status = _tool_status(event)
    line = f"[{_event_phase(event)} #{event.sequence}] tool {status}: {_tool_name(event)}"
    if event.tool_arguments is not None:
        line = f"{line} args={_compact(event.tool_arguments, limit=320)}"

    duration_ms = _duration_ms(event)
    if duration_ms is not None:
        line = f"{line} duration={duration_ms}ms"

    failure_category = event.payload.get("failure_category")
    if failure_category:
        line = f"{line} failure_category={_compact(failure_category, limit=120)}"

    error_message = event.payload.get("error_message") or (event.message if event.type == "tool_call_failed" else None)
    if error_message:
        line = f"{line} error={_compact(error_message, limit=240)}"

    artifacts = _artifact_summary(event.payload)
    output_hint = _output_hint(event.payload)
    if artifacts:
        line = f"{line} artifacts={artifacts}"
    elif output_hint:
        line = f"{line} {output_hint}"
    elif _should_show_output_preview(event):
        line = f"{line} output={_compact(event.tool_output_preview, limit=240)}"
    elif event.tool_output_preview and not error_message:
        line = f"{line} output=omitted"
    return line


def _event_phase(event: RunEvent) -> str:
    text = f"{event.title} {event.message}".lower()
    if event.task_id == "pre-plan" or "pre-plan" in text:
        return "PRE-PLAN"
    if event.payload.get("report_path") or "report" in text:
        return "REPORT"
    if "verification" in text or event.payload.get("tool_name") == "openai_agents.verifier":
        return "VERIFICATION"
    if any(marker in text for marker in ("runtime startup", "provider setup", "harness setup", "tool setup", "sdk agent ready")):
        return "STARTUP"
    if event.type in {"run_started", "run_completed", "run_failed"}:
        return "RUN"
    return "EXECUTION"


def _event_status(event: RunEvent) -> str:
    title = event.title.lower()
    if event.type == "run_failed" or "failed" in title:
        return "failed"
    if "started" in title or event.type in {"run_started", "agent_started", "planning_started"}:
        return "started"
    if "completed" in title or event.type in {"run_completed", "step_completed"}:
        return "completed"
    return "update"


def _tool_status(event: RunEvent) -> str | None:
    status = event.payload.get("status")
    runner_result = event.payload.get("runner_result")
    if status is None and isinstance(runner_result, dict):
        status = runner_result.get("status")
    if status is not None:
        return str(status).lower()
    if event.type == "tool_call_started":
        return "started"
    if event.type == "tool_call_failed":
        return "failed"
    if event.type == "tool_call_completed":
        return "completed"
    return None


def _tool_name(event: RunEvent) -> str:
    for value in (event.tool_name, event.payload.get("tool_name"), event.payload.get("capability_name")):
        if value:
            return str(value)
    return "unknown"


def _duration_ms(event: RunEvent) -> int | None:
    if event.duration_ms is not None:
        return event.duration_ms
    payload_duration = event.payload.get("duration_ms")
    return payload_duration if isinstance(payload_duration, int) else None


def _artifact_summary(payload: dict[str, Any]) -> str | None:
    refs = payload.get("artifact_refs")
    kinds: list[str] = []
    if isinstance(refs, list):
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            kind = ref.get("kind")
            if kind and str(kind) not in kinds:
                kinds.append(str(kind))
    if kinds:
        return ",".join(kinds)
    artifact_path = payload.get("artifact_path")
    return str(artifact_path) if artifact_path else None


def _output_hint(payload: dict[str, Any]) -> str | None:
    for key, label in (
        ("report_path", "report"),
        ("run_output_path", "run_output"),
        ("output_path", "output"),
        ("events_path", "events"),
    ):
        value = payload.get(key)
        if value:
            return f"{label}={_compact(value, limit=240)}"
    return None


def _should_show_output_preview(event: RunEvent) -> bool:
    if not event.tool_output_preview:
        return False
    has_summary = any(
        key in event.payload
        for key in (
            "status",
            "runner_result",
            "artifact_refs",
            "artifact_path",
            "report_path",
            "run_output_path",
            "output_path",
            "events_path",
            "failure_category",
            "error_message",
        )
    )
    return not has_summary and len(event.tool_output_preview) <= 240


def _compact(value: object, limit: int = 1000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")) if not isinstance(value, str) else value
    text = text.replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}..."
