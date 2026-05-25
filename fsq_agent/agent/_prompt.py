from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError

from fsq_agent.models import AgentFinalOutput, AgentTaskInput, ConfigurationError, KnowledgeBundle, OpenAIAgentPromptConfig, SkillBundle, Task


_DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_AGENT_TEMPLATE = _DEFAULT_TEMPLATE_DIR / "agent_instructions.j2"
_DEFAULT_TASK_TEMPLATE = _DEFAULT_TEMPLATE_DIR / "task_input.j2"


@dataclass(frozen=True)
class PromptKeyValue:
    key: str
    value: str


@dataclass(frozen=True)
class PromptSkill:
    name: str
    instructions: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentPromptModel:
    custom_instructions: list[str] = field(default_factory=list)
    private_knowledge: list[PromptKeyValue] = field(default_factory=list)
    knowledge_warnings: list[str] = field(default_factory=list)
    skills: list[PromptSkill] = field(default_factory=list)
    final_output_schema_json: str = ""
    variables: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPromptModel:
    id: str
    name: str
    description: str
    acceptance_criteria: list[str] = field(default_factory=list)
    key_actions: list[str] = field(default_factory=list)
    verification_criteria: list[dict[str, Any]] = field(default_factory=list)
    input_json: str = ""
    variables: dict[str, Any] = field(default_factory=dict)


class PromptModelBuilder:
    def __init__(self, settings: OpenAIAgentPromptConfig) -> None:
        self.settings = settings

    def build_agent_prompt(self, knowledge: KnowledgeBundle, skills: list[SkillBundle]) -> AgentPromptModel:
        return AgentPromptModel(
            custom_instructions=self._custom_instructions(),
            private_knowledge=[PromptKeyValue(key=key, value=str(value)) for key, value in knowledge.items.items()],
            knowledge_warnings=list(knowledge.warnings),
            skills=[
                PromptSkill(
                    name=skill.name,
                    instructions=skill.instructions or "",
                    warnings=list(skill.warnings),
                )
                for skill in skills
            ],
            final_output_schema_json=json.dumps(AgentFinalOutput.model_json_schema(), indent=2, ensure_ascii=False),
            variables=dict(self.settings.variables),
        )

    def _custom_instructions(self) -> list[str]:
        instructions = list(self.settings.custom_instructions)
        if self.settings.custom_instructions_path is None:
            return instructions
        path = self.settings.custom_instructions_path.expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ConfigurationError("Custom instructions file does not exist.", context={"path": str(path)})
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise ConfigurationError("Unable to read custom instructions file.", context={"path": str(path)}) from exc
        if content:
            instructions.extend(part.strip() for part in content.split("\n\n") if part.strip())
        return instructions

    def build_task_prompt(self, task: Task, runtime_policy: list[str] | None = None) -> TaskPromptModel:
        acceptance_policy = (
            "Use the provided key actions as execution guidance and the structured verification criteria as final success criteria."
            if task.key_actions or task.verification_criteria
            else (
                "Use the provided task acceptance criteria as required success criteria."
                if task.acceptance_criteria
                else "Derive acceptance criteria from the task description, private knowledge, and loaded skills. If the task is too broad, use successful flow completion with enough evidence as the success standard."
            )
        )
        task_input = AgentTaskInput(
            task=task,
            acceptance_criteria=list(task.acceptance_criteria),
            key_actions=list(task.key_actions),
            verification_criteria=list(task.verification_criteria),
            runtime_policy=list(runtime_policy or []),
            acceptance_policy=acceptance_policy,
        )
        return TaskPromptModel(
            id=task.id,
            name=task.name,
            description=task.description,
            acceptance_criteria=list(task.acceptance_criteria),
            key_actions=list(task.key_actions),
            verification_criteria=[criterion.model_dump(mode="json") for criterion in task.verification_criteria],
            input_json=task_input.model_dump_json(indent=2),
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
