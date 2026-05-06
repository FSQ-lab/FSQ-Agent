from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ToolKind = Literal["mcp", "cli", "file"]
ToolStatus = Literal["success", "failed", "skipped"]
MCPTransport = Literal["stdio", "streamable_http", "sse", "hosted"]


class MCPServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    transport: MCPTransport = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path | None = None
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    require_approval: Any = "never"
    load_prompts: bool = False
    cache_tools_list: bool = True
    timeout_seconds: int | None = Field(default=None, ge=1)
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)


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