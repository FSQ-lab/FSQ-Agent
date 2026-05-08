from fsq_agent.models import ExecutionStep, OpenAIAgentsSettings, ShellSettings, SkillConfig, Task


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


def test_openai_agents_settings_defaults_to_safe_offline_mode() -> None:
    settings = OpenAIAgentsSettings()

    assert settings.enabled is False
    assert settings.model == "gpt-5.4"
    assert settings.api_key_env == "AZURE_OPENAI_API_KEY"


def test_skill_config_defaults_to_markdown() -> None:
    skill = SkillConfig(name="browser-testing", path="browser-testing.md")

    assert skill.kind == "markdown"
    assert skill.required is False


def test_shell_settings_defaults_to_disabled_allowlist() -> None:
    settings = ShellSettings()

    assert settings.enabled is False
    assert settings.mode == "allowlist"
    assert settings.command_allowlist == []