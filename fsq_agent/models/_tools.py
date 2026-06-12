from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ToolKind = Literal["cli", "file", "harness", "shell"]
ToolStatus = Literal["success", "failed", "skipped"]


class CLIToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    description: str = ""
    timeout_seconds: int | None = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: ToolKind
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    server_name: str | None = None
    command: str | None = None


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    kind: ToolKind | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    status: ToolStatus
    output: Any = None
    error: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    raw: Any = None