import json
import logging

from fsq_agent.models import RunEvent, TaskResult


logger = logging.getLogger(__name__)


def log_result(result: TaskResult) -> None:
    logger.info("Task %s: %s", result.task_id, result.status)
    logger.info("Report: %s", result.report.path)


def log_run_event(event: RunEvent, stream_format: str = "rich") -> None:
    if stream_format == "jsonl":
        logger.info(json.dumps(event.model_dump(mode="json"), ensure_ascii=False), extra={"fsq_raw_message": True})
        return

    log = _event_logger(event)
    prefix = f"[{event.sequence}] {event.title}"
    if event.type in {"tool_call_started", "tool_call_completed", "tool_call_failed"} and event.tool_name:
        prefix = f"{prefix}: {event.tool_name}"
    log(prefix)
    if event.message:
        log("  %s", event.message)
    if event.tool_arguments is not None:
        log("  args: %s", _compact(event.tool_arguments))
    if event.tool_output_preview:
        log("  output: %s", event.tool_output_preview)
    if event.duration_ms is not None:
        log("  duration: %sms", event.duration_ms)


def _event_logger(event: RunEvent):
    if event.type in {"tool_call_failed", "run_failed"}:
        return logger.error
    return logger.info


def _compact(value: object, limit: int = 1000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
    text = text.replace("\r", " ").replace("\n", " ")
    return text if len(text) <= limit else f"{text[:limit]}..."
