from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from fsq_agent.models._task import VerificationMode


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "fsq-agent"
    model: str = "gpt-5.4"
    max_steps: int = Field(default=50, ge=1)
    step_timeout_seconds: int = Field(default=60, ge=1)
    max_retries: int = Field(default=3, ge=0)


class ContextTrimmingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    recent_turns: int = Field(default=2, ge=1)
    max_tool_output_chars: int = Field(default=8000, ge=1)
    preview_chars: int = Field(default=1000, ge=0)
    trimmable_tools: list[str] = Field(default_factory=list)


class LocalToolOutputSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_enabled: bool = True
    always_write_artifact: bool = True
    artifact_subdir: str = "artifacts/tools"
    recent_full_output_count: int = Field(default=3, ge=0)
    full_output_max_chars: int = Field(default=30000, ge=1)
    historical_output_mode: Literal["artifact_reference"] = "artifact_reference"
    historical_preview_chars: int = Field(default=1000, ge=0)
    model_response_max_chars: int = Field(default=4000, ge=500)

    @field_validator("artifact_subdir")
    @classmethod
    def validate_artifact_subdir(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("artifact_subdir must be a relative path inside the run directory")
        return value


class VerificationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: VerificationMode = "normal"


class RuntimeSecretSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_env_names: list[str] = Field(default_factory=list)


class PrePlanSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_dir: Path | None = None


class AndroidHarnessSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: Literal["uiautomator2"] = "uiautomator2"
    app_id: str | None = None
    serial: str | None = None


class HarnessSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["android"] = "android"
    android: AndroidHarnessSettings = Field(default_factory=AndroidHarnessSettings)


class OpenAIAgentPromptConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_template_path: Path | None = None
    task_template_path: Path | None = None
    custom_instructions_path: Path | None = None
    custom_instructions: list[str] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)


class OpenAIAgentsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["azure_openai", "github_copilot"] = "azure_openai"
    base_url: str = "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/"
    api_key_env: str = "AZURE_OPENAI_API_KEY"
    model: str = "gpt-5.4"
    max_turns: int = Field(default=50, ge=1)
    tracing_enabled: bool = False
    trace_include_sensitive_data: bool = False
    fail_without_api_key: bool = True
    prompt: OpenAIAgentPromptConfig = Field(default_factory=OpenAIAgentPromptConfig)
    context_trimming: ContextTrimmingSettings = Field(default_factory=ContextTrimmingSettings)
    local_tool_output: LocalToolOutputSettings = Field(default_factory=LocalToolOutputSettings)


class ShellSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    mode: Literal["allowlist", "allow_all"] = "allowlist"
    command_allowlist: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, ge=1)
    working_dir: Path = Path(".")


class DeprecatedToolSettings(BaseModel):
    model_config = ConfigDict(extra="allow")


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_dir: Path | None = None
    marker_file: str = ".fsq-agent-workspace"
    auto_init: bool = True


class CaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dir: Path = Path("./cases")


class OutputSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_dir: Path = Path("output")
    runs_dir: Path = Path("runs")