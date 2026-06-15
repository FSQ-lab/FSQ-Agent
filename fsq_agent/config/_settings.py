from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models import (
    AgentSettings,
    CaseSettings,
    HarnessSettings,
    OpenAIAgentsSettings,
    OutputSettings,
    PrePlanSettings,
    RuntimeSecretSettings,
    SkillConfig,
    WorkspaceSettings,
)
from fsq_agent.models._settings import DeprecatedToolSettings


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentSettings = Field(default_factory=AgentSettings)
    openai_agents: OpenAIAgentsSettings = Field(default_factory=OpenAIAgentsSettings)
    harness: HarnessSettings = Field(default_factory=HarnessSettings)
    runtime_secrets: RuntimeSecretSettings = Field(default_factory=RuntimeSecretSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    cases: CaseSettings = Field(default_factory=CaseSettings)
    cli_tools: list[DeprecatedToolSettings] = Field(default_factory=list, exclude=True)
    shell: DeprecatedToolSettings = Field(default_factory=DeprecatedToolSettings, exclude=True)
    skills: list[SkillConfig] = Field(default_factory=list)
    output: OutputSettings = Field(default_factory=OutputSettings)
    pre_plan: PrePlanSettings = Field(default_factory=PrePlanSettings)
    knowledge_dir: Path = Path("./knowledge")