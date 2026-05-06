from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from auto_test_agent.models import (
    AgentSettings,
    CLIToolConfig,
    MCPServerConfig,
    ObservationSettings,
    OpenAIAgentsSettings,
    OutputSettings,
    ShellSettings,
    SkillConfig,
)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentSettings = Field(default_factory=AgentSettings)
    openai_agents: OpenAIAgentsSettings = Field(default_factory=OpenAIAgentsSettings)
    mcp_servers: list[MCPServerConfig] = Field(default_factory=list)
    cli_tools: list[CLIToolConfig] = Field(default_factory=list)
    shell: ShellSettings = Field(default_factory=ShellSettings)
    skills: list[SkillConfig] = Field(default_factory=list)
    observation: ObservationSettings = Field(default_factory=ObservationSettings)
    output: OutputSettings = Field(default_factory=OutputSettings)
    knowledge_dir: Path = Path("./knowledge")