from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CommonToolStatus = Literal["success", "failed", "skipped"]
ToolKind = Literal["common", "cli", "file", "harness", "shell"]
ToolStatus = Literal["success", "failed", "skipped"]


class CommonToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    params_json_schema: dict[str, Any] = Field(default_factory=dict)
    strict: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommonToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommonToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    status: CommonToolStatus
    output: Any = None
    artifact_path: Path | str | None = None
    artifact_content_chars: int | None = Field(default=None, ge=0)
    model_output: Literal["full", "artifact_reference"] = "full"
    sensitive: bool = False
    error: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    raw: Any = None


class CLIToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    command: str
    args: list[str] = Field(default_factory=list)
    description: str = ""
    timeout_seconds: int | None = None


class ToolDefinition(CommonToolDefinition):
    model_config = ConfigDict(extra="forbid")

    kind: ToolKind = "common"
    input_schema: dict[str, Any] = Field(default_factory=dict)
    server_name: str | None = None
    command: str | None = None


class ToolCall(CommonToolCall):
    model_config = ConfigDict(extra="forbid")

    kind: ToolKind | None = None


class ToolResult(CommonToolResult):
    model_config = ConfigDict(extra="forbid")