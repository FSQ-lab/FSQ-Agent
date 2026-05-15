from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models import (
    AgentSettings,
    CaseSettings,
    CLIToolConfig,
    LifecycleControllerSettings,
    MCPServerConfig,
    MCPToolValidationSettings,
    OpenAIAgentsSettings,
    OutputSettings,
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
    lifecycle: LifecycleControllerSettings = Field(default_factory=LifecycleControllerSettings)
    verification: VerificationSettings = Field(default_factory=VerificationSettings)
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    mcp_tool_validation: MCPToolValidationSettings = Field(default_factory=MCPToolValidationSettings)
    runtime_secrets: RuntimeSecretSettings = Field(default_factory=RuntimeSecretSettings)
    workspace: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    cases: CaseSettings = Field(default_factory=CaseSettings)
    cli_tools: list[CLIToolConfig] = Field(default_factory=list)
    shell: ShellSettings = Field(default_factory=ShellSettings)
    skills: list[SkillConfig] = Field(default_factory=list)
    output: OutputSettings = Field(default_factory=OutputSettings)
    knowledge_dir: Path = Path("./knowledge")