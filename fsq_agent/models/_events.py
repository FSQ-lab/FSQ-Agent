from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


RunEventType: TypeAlias = Literal[
    "run_started",
    "agent_started",
    "planning_started",
    "planning_update",
    "reasoning_summary",
    "mcp_tools_listed",
    "tool_call_started",
    "tool_call_completed",
    "tool_call_failed",
    "harness_setup_started",
    "harness_setup_completed",
    "harness_setup_failed",
    "harness_teardown_started",
    "harness_teardown_completed",
    "harness_teardown_failed",
    "platform_action_started",
    "platform_action_completed",
    "platform_action_failed",
    "step_completed",
    "run_completed",
    "run_failed",
]


class RunEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    task_id: str
    type: RunEventType
    title: str
    sequence: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: str = ""
    tool_name: str | None = None
    tool_call_id: str | None = None
    tool_arguments: dict[str, Any] | str | None = None
    tool_output_preview: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


RunEventSink: TypeAlias = Callable[[RunEvent], Awaitable[None] | None]
