from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ScreenshotSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    format: Literal["png", "jpg", "jpeg"] = "png"
    quality: int = Field(default=85, ge=1, le=100)


class UITreeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    max_depth: int = Field(default=10, ge=1)


class LoggingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: str = "INFO"
    format: Literal["json", "text"] = "json"


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "auto-test-agent"
    model: str = "gpt-5.4"
    max_steps: int = Field(default=50, ge=1)
    step_timeout_seconds: int = Field(default=60, ge=1)
    max_retries: int = Field(default=3, ge=0)


class OpenAIAgentsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    base_url: str = "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/"
    api_key_env: str = "AZURE_OPENAI_API_KEY"
    model: str = "gpt-5.4"
    max_turns: int = Field(default=50, ge=1)
    tracing_enabled: bool = False
    trace_include_sensitive_data: bool = False
    use_responses: bool = True
    fail_without_api_key: bool = True


class ShellSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    mode: Literal["allowlist", "allow_all"] = "allowlist"
    command_allowlist: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, ge=1)
    working_dir: Path = Path(".")


class ObservationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    screenshot: ScreenshotSettings = Field(default_factory=ScreenshotSettings)
    ui_tree: UITreeSettings = Field(default_factory=UITreeSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


class OutputSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logs_dir: Path = Path("./logs")
    reports_dir: Path = Path("./reports")
    screenshots_dir: Path = Path("./screenshots")
    traces_dir: Path = Path("./logs/traces")