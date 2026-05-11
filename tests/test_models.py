import pytest

from fsq_agent.models import AgentFinalOutput, AgentTaskInput, ExecutionStep, LifecycleControllerSettings, LocalToolOutputSettings, OpenAIAgentsSettings, ShellSettings, SkillConfig, Task


def test_task_defaults() -> None:
    task = Task(description="Do a thing")

    assert task.id == "task"
    assert task.name == "Task"
    assert task.acceptance_criteria == []
    assert task.timeout_seconds == 300
    assert task.max_retries == 3
    assert task.knowledge_refs == []


def test_execution_step_requires_positive_id() -> None:
    step = ExecutionStep(
        step_id=1,
        action="write",
        tool="file.write",
        tool_input={"path": "out.txt", "content": "ok"},
        expected_outcome="file written",
    )

    assert step.step_id == 1


def test_agent_final_output_defaults_schema_version() -> None:
    output = AgentFinalOutput(status="success", summary="Done")

    assert output.schema_version == "task_run_v1"
    assert output.pre_plan == []


def test_agent_task_input_wraps_task_contract() -> None:
    task = Task(id="task-1", description="Do a thing", acceptance_criteria=["Done."])
    task_input = AgentTaskInput(
        task=task,
        acceptance_criteria=task.acceptance_criteria,
        acceptance_policy="Use provided criteria.",
    )

    assert task_input.schema_version == "task_input_v1"
    assert task_input.output_contract == "task_run_v1"
    assert task_input.task.id == "task-1"


def test_openai_agents_settings_defaults_to_safe_offline_mode() -> None:
    settings = OpenAIAgentsSettings()

    assert settings.enabled is False
    assert settings.model == "gpt-5.4"
    assert settings.api_key_env == "AZURE_OPENAI_API_KEY"
    assert settings.prompt.custom_instructions == []
    assert settings.prompt.agent_template_path is None
    assert settings.prompt.task_template_path is None
    assert settings.prompt.variables == {}
    assert settings.context_trimming.enabled is True
    assert settings.context_trimming.max_tool_output_chars == 8000
    assert settings.local_tool_output.always_write_artifact is True
    assert settings.local_tool_output.full_output_max_chars == 30000


def test_lifecycle_controller_settings_default_to_noop() -> None:
    settings = LifecycleControllerSettings()

    assert settings.controller == "none"
    assert settings.options == {}


def test_skill_config_defaults_to_markdown() -> None:
    skill = SkillConfig(name="browser-testing", path="browser-testing.md")

    assert skill.kind == "markdown"
    assert skill.required is False


def test_shell_settings_defaults_to_disabled_allowlist() -> None:
    settings = ShellSettings()

    assert settings.enabled is False
    assert settings.mode == "allowlist"
    assert settings.command_allowlist == []


def test_local_tool_output_rejects_artifact_subdir_escape() -> None:
    with pytest.raises(ValueError, match="artifact_subdir"):
        LocalToolOutputSettings(artifact_subdir="../outside")
