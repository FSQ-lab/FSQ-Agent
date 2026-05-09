from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from fsq_agent.models import ConfigurationError, KnowledgeBundle, OpenAIAgentPromptConfig, SkillBundle, Task


_DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_AGENT_TEMPLATE = _DEFAULT_TEMPLATE_DIR / "agent_instructions.j2"
_DEFAULT_TASK_TEMPLATE = _DEFAULT_TEMPLATE_DIR / "task_input.j2"


@dataclass(frozen=True)
class PromptKeyValue:
    key: str
    value: str


@dataclass(frozen=True)
class PromptFlowTemplate:
    name: str
    template: str


@dataclass(frozen=True)
class PromptSkill:
    name: str
    instructions: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentPromptModel:
    custom_instructions: list[str] = field(default_factory=list)
    private_knowledge: list[PromptKeyValue] = field(default_factory=list)
    flow_templates: list[PromptFlowTemplate] = field(default_factory=list)
    knowledge_warnings: list[str] = field(default_factory=list)
    skills: list[PromptSkill] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPromptModel:
    id: str
    name: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)


class PromptModelBuilder:
    def __init__(self, settings: OpenAIAgentPromptConfig) -> None:
        self.settings = settings

    def build_agent_prompt(self, knowledge: KnowledgeBundle, skills: list[SkillBundle]) -> AgentPromptModel:
        return AgentPromptModel(
            custom_instructions=list(self.settings.custom_instructions),
            private_knowledge=[PromptKeyValue(key=key, value=str(value)) for key, value in knowledge.items.items()],
            flow_templates=[PromptFlowTemplate(name=name, template=str(template)) for name, template in knowledge.flow_templates.items()],
            knowledge_warnings=list(knowledge.warnings),
            skills=[
                PromptSkill(
                    name=skill.name,
                    instructions=skill.instructions or "",
                    warnings=list(skill.warnings),
                )
                for skill in skills
            ],
            variables=dict(self.settings.variables),
        )

    def build_task_prompt(self, task: Task) -> TaskPromptModel:
        return TaskPromptModel(
            id=task.id,
            name=task.name,
            description=task.description,
            acceptance_criteria=list(task.acceptance_criteria),
            variables=dict(self.settings.variables),
        )


class PromptRenderer:
    def __init__(self, settings: OpenAIAgentPromptConfig) -> None:
        self.settings = settings

    def render_agent_prompt(self, model: AgentPromptModel) -> str:
        return self._render_template(self.settings.agent_template_path or _DEFAULT_AGENT_TEMPLATE, asdict(model))

    def render_task_prompt(self, model: TaskPromptModel) -> str:
        return self._render_template(self.settings.task_template_path or _DEFAULT_TASK_TEMPLATE, {"task": asdict(model)})

    def _render_template(self, path: Path, context: dict[str, Any]) -> str:
        template_path = path.expanduser().resolve()
        if not template_path.exists() or not template_path.is_file():
            raise ConfigurationError("Prompt template file does not exist.", context={"path": str(template_path)})
        environment = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        try:
            return environment.get_template(template_path.name).render(**context).strip()
        except TemplateError as exc:
            raise ConfigurationError("Unable to render prompt template.", context={"path": str(template_path)}) from exc
