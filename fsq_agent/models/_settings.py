from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from fsq_agent.models._skills import SkillConfig


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "fsq-agent"
    step_timeout_seconds: int = Field(default=60, ge=1)


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


class RuntimeSecretSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_env_names: list[str] = Field(default_factory=list)


class PrePlanSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_dir: Path | None = None


class PrePlanKnowledgeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dir: Path | None = None


class KnowledgeSkillSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dir: Path = Path("skills")
    items: list[SkillConfig] = Field(default_factory=list)


class AgentKnowledgeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_dir: Path = Path("./knowledge")
    skills: KnowledgeSkillSettings = Field(default_factory=KnowledgeSkillSettings)
    pre_plan: PrePlanKnowledgeSettings = Field(default_factory=PrePlanKnowledgeSettings)


class AgentContextSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge: AgentKnowledgeSettings = Field(default_factory=AgentKnowledgeSettings)


class AndroidHarnessSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: Literal["uiautomator2"] = "uiautomator2"
    _app_id: str | None = PrivateAttr(default=None)
    _serial: str | None = PrivateAttr(default=None)

    @property
    def app_id(self) -> str | None:
        return self._app_id

    @app_id.setter
    def app_id(self, value: str | None) -> None:
        self._app_id = value

    @property
    def serial(self) -> str | None:
        return self._serial

    @serial.setter
    def serial(self, value: str | None) -> None:
        self._serial = value


class StrictCoreHarnessSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_interval_seconds: float = Field(default=1.0, ge=0)


class HarnessSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["android"] = "android"
    android: AndroidHarnessSettings = Field(default_factory=AndroidHarnessSettings)
    strict_core: StrictCoreHarnessSettings = Field(default_factory=StrictCoreHarnessSettings)


class OpenAIAgentPromptConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_template_path: Path | None = None
    task_template_path: Path | None = None
    variables: dict[str, Any] = Field(default_factory=dict)


class OpenAIAgentsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["azure_openai", "github_copilot"] = "github_copilot"
    max_turns: int = Field(default=50, ge=1)
    tracing_enabled: bool = True
    prompt: OpenAIAgentPromptConfig = Field(default_factory=OpenAIAgentPromptConfig)
    _base_url: str = PrivateAttr(default="")
    _model: str = PrivateAttr(default="gpt-5.5")
    _context_trimming: ContextTrimmingSettings = PrivateAttr(default_factory=ContextTrimmingSettings)
    _local_tool_output: LocalToolOutputSettings = PrivateAttr(default_factory=LocalToolOutputSettings)

    @property
    def base_url(self) -> str:
        return self._base_url

    @base_url.setter
    def base_url(self, value: str) -> None:
        self._base_url = value

    @property
    def api_key_env(self) -> str:
        return "AZURE_OPENAI_API_KEY"

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value

    @property
    def context_trimming(self) -> ContextTrimmingSettings:
        return self._context_trimming

    @context_trimming.setter
    def context_trimming(self, value: ContextTrimmingSettings | dict[str, Any]) -> None:
        self._context_trimming = ContextTrimmingSettings.model_validate(value)

    @property
    def local_tool_output(self) -> LocalToolOutputSettings:
        return self._local_tool_output

    @local_tool_output.setter
    def local_tool_output(self, value: LocalToolOutputSettings | dict[str, Any]) -> None:
        self._local_tool_output = LocalToolOutputSettings.model_validate(value)


class WorkspaceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_dir: Path | None = None
    _marker_file: str = PrivateAttr(default=".fsq-agent-workspace")
    _auto_init: bool = PrivateAttr(default=True)

    @property
    def marker_file(self) -> str:
        return self._marker_file

    @property
    def auto_init(self) -> bool:
        return self._auto_init


class CaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dir: Path = Path("./cases")


class OutputSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_dir: Path = Path("output")
    _runs_dir: Path = PrivateAttr(default=Path("runs"))

    @property
    def runs_dir(self) -> Path:
        return self._runs_dir

    @runs_dir.setter
    def runs_dir(self, value: str | Path) -> None:
        self._runs_dir = Path(value)