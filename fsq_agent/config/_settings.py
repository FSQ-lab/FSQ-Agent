from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models import (
    AgentSettings,
    CaseSettings,
    CLIToolConfig,
    HarnessSettings,
    OpenAIAgentsSettings,
    OutputSettings,
    PrePlanSettings,
    RuntimeSecretSettings,
    ShellSettings,
    SkillConfig,
    VerificationSettings,
    WorkspaceSettings,
)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentSettings = Field(default_factory=AgentSettings)
    openai_agents: OpenAIAgentsSettings = Field(default_factory=OpenAIAgentsSettings)
    harness: HarnessSettings = Field(default_factory=HarnessSettings)
    verification: VerificationSettings = Field(default_factory=VerificationSettings)
    runtime_secrets: RuntimeSecretSettings = Field(default_factory=RuntimeSecretSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    cases: CaseSettings = Field(default_factory=CaseSettings)
    cli_tools: list[CLIToolConfig] = Field(default_factory=list)
    shell: ShellSettings = Field(default_factory=ShellSettings)
    skills: list[SkillConfig] = Field(default_factory=list)
    output: OutputSettings = Field(default_factory=OutputSettings)
    pre_plan: PrePlanSettings = Field(default_factory=PrePlanSettings)
    knowledge_dir: Path = Path("./knowledge")