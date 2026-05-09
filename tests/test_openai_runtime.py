from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import pytest

from fsq_agent.agent import OpenAIAgentsRuntime
from fsq_agent.agent._prompt import PromptModelBuilder, PromptRenderer
from fsq_agent.config import Settings
from fsq_agent.models import (
    KnowledgeBundle,
    LocalToolOutputSettings,
    MCPToolValidationIssue,
    OpenAIAgentsSettings,
    OutputSettings,
    Task,
)


class _EmptyToolFactory:
    def build_tools(self) -> list[Any]:
        return []


class _FailingMCPFactory:
    async def enter_servers(self, _stack: AsyncExitStack) -> tuple[list[Any], list[Any]]:
        raise RuntimeError("MCP startup failed")


class _DiagnosticMCPFactory:
    def get_validation_issues(self) -> list[MCPToolValidationIssue]:
        return [
            MCPToolValidationIssue(
                server_name="appium-mcp",
                tool_name="appium_driver_settings",
                reason="Unsupported JSON Schema keyword: propertyNames",
                policy="auto_ignore",
                schema_path="$.propertyNames",
            )
        ]


@pytest.mark.asyncio
async def test_runtime_failure_returns_failed_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    task = Task(
        id="runtime-failure",
        name="Runtime Failure",
        description="Trigger MCP failure.",
        acceptance_criteria=["A failed step is returned."],
    )

    results = await runtime.run_task(task, KnowledgeBundle(), [], "runtime-failure-2026-05-09_00-00-00")

    assert results[0].status == "failed"
    assert results[0].tool_name == "openai_agents.runner"
    assert "MCP startup failed" in str(results[0].error)


def test_runtime_builds_step_results_from_structured_pre_plan() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    final_output = """
{
    "status": "failed",
    "summary": "Could not finish.",
    "pre_plan": [
        {
            "step_id": 1,
            "action": "Open browser",
            "success_criteria": ["Browser is open"],
            "status": "success"
        },
        {
            "step_id": 2,
            "action": "Add page to favorites",
            "success_criteria": ["Page is favorited"],
            "status": "adjusted"
        }
    ],
    "plan_updates": ["Used keyboard shortcut after toolbar button was unavailable."],
    "satisfied_criteria": ["Browser is open"],
    "unmet_criteria": ["Page is favorited"],
    "evidence": [],
    "errors": []
}
"""

    steps = runtime._build_pre_plan_step_results(final_output, duration_ms=123)

    assert [step.step_id for step in steps] == [1, 2]
    assert [step.status for step in steps] == ["success", "adjusted"]
    assert steps[0].tool_name == "pre_plan"
    assert "Browser is open" in steps[0].actual_outcome
    assert "Used keyboard shortcut" in steps[1].actual_outcome


def test_runtime_task_input_requests_derived_acceptance_criteria() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    task = Task(id="derive", name="Derive", description="Open the page and verify it loads.")

    task_input = runtime._build_task_input(task)

    assert "Task acceptance criteria: none" in task_input
    assert "Derive acceptance criteria" in task_input


def test_runtime_instructions_include_custom_operator_instructions() -> None:
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(
            enabled=True,
            prompt={"custom_instructions": ["Prefer accessibility locators before coordinate-based actions."]},
        )
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())

    instructions = runtime._build_instructions(KnowledgeBundle(), [])

    assert "Custom operator instructions:" in instructions
    assert "Prefer accessibility locators before coordinate-based actions." in instructions


def test_runtime_instructions_use_configured_prompt_templates(tmp_path: Path) -> None:
    agent_template = tmp_path / "agent.j2"
    task_template = tmp_path / "task.j2"
    agent_template.write_text(
        "Configured base instruction.\n"
        "Configured knowledge:\n"
        "{% for item in private_knowledge %}- {{ item.key }}={{ item.value }}\n{% endfor %}"
        "Configured flows:\n"
        "{% for flow in flow_templates %}- {{ flow.name }}={{ flow.template }}\n{% endfor %}",
        encoding="utf-8",
    )
    task_template.write_text(
        "Task {{ task.id }}: {{ task.description }}\n"
        "{% if task.acceptance_criteria %}{{ task.acceptance_criteria | join(', ') }}{% else %}Configured no criteria text.{% endif %}\n",
        encoding="utf-8",
    )
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(
            enabled=True,
            prompt={
                "agent_template_path": agent_template,
                "task_template_path": task_template,
            },
        )
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    knowledge = KnowledgeBundle(items={"k": "v"}, flow_templates={"flow": "steps"})

    instructions = runtime._build_instructions(knowledge, [])
    task_input = runtime._build_task_input(Task(id="t1", description="Do it."))

    assert instructions.startswith("Configured base instruction.")
    assert "Configured knowledge:" in instructions
    assert "Configured flows:" in instructions
    assert task_input == "Task t1: Do it.\nConfigured no criteria text."


def test_prompt_model_builder_and_renderer_use_templates() -> None:
    settings = OpenAIAgentsSettings(enabled=True, prompt={"custom_instructions": ["Custom."]}).prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [])
    task_model = builder.build_task_prompt(Task(id="task-1", description="Do it.", acceptance_criteria=["Done."]))

    assert "Custom operator instructions:" in renderer.render_agent_prompt(agent_model)
    assert "- Custom." in renderer.render_agent_prompt(agent_model)
    assert "Task ID: task-1" in renderer.render_task_prompt(task_model)
    assert "- Done." in renderer.render_task_prompt(task_model)


def test_prompt_renderer_injects_model_into_configured_jinja_templates(tmp_path: Path) -> None:
    agent_template = tmp_path / "agent.j2"
    task_template = tmp_path / "task.j2"
    agent_template.write_text("{{ variables.prefix }}{% for instruction in custom_instructions %} {{ instruction }}{% endfor %}", encoding="utf-8")
    task_template.write_text("Task {{ task.id }} {{ task.variables.prefix }}", encoding="utf-8")
    settings = OpenAIAgentsSettings(
        enabled=True,
        prompt={
            "agent_template_path": agent_template,
            "task_template_path": task_template,
            "custom_instructions": ["Custom."],
            "variables": {"prefix": "Base."},
        },
    ).prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [])
    task_model = builder.build_task_prompt(Task(id="task-1", description="Do it.", acceptance_criteria=["Done."]))

    assert renderer.render_agent_prompt(agent_model) == "Base. Custom."
    assert renderer.render_task_prompt(task_model) == "Task task-1 Base."


def test_runtime_builds_mcp_validation_diagnostic_steps() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _DiagnosticMCPFactory())

    steps = runtime._build_mcp_validation_steps()

    assert steps[0].status == "skipped"
    assert steps[0].tool_name == "mcp_tool_validation"
    assert "appium-mcp.appium_driver_settings" in steps[0].actual_outcome
    assert steps[0].tool_output["schema_path"] == "$.propertyNames"


def test_runtime_builds_run_config_with_tool_output_trimmer() -> None:
    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())

    run_config = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider")

    assert run_config.kwargs["model_provider"] == "provider"
    input_filter = run_config.kwargs["call_model_input_filter"]
    assert input_filter.recent_tool_outputs == 3
    assert input_filter.sdk_filter.kwargs == {
        "recent_turns": 2,
        "max_output_chars": 8000,
        "preview_chars": 1000,
        "trimmable_tools": None,
    }


def test_runtime_tool_count_filter_keeps_recent_outputs_and_trims_history() -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider").kwargs["call_model_input_filter"]
    old_output = "old-output " * 1000
    recent_output = "recent-output " * 1000
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "1", "name": "read_file"},
                {"type": "function_call_output", "call_id": "1", "output": old_output},
                {"type": "function_call", "call_id": "2", "name": "read_file"},
                {"type": "function_call_output", "call_id": "2", "output": "recent 1"},
                {"type": "function_call", "call_id": "3", "name": "read_file"},
                {"type": "function_call_output", "call_id": "3", "output": "recent 2"},
                {"type": "function_call", "call_id": "4", "name": "read_file"},
                {"type": "function_call_output", "call_id": "4", "output": recent_output},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input[1]["output"].startswith("[Trimmed historical read_file output")
    assert filtered.input[7]["output"] == recent_output


def test_runtime_tool_count_filter_writes_artifact_for_trimmed_history(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from agents.run_config import ModelInputData

    class _RunConfig:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _ToolOutputTrimmer:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def __call__(self, data: Any) -> Any:
            return data.model_data

    settings = Settings(
        openai_agents=OpenAIAgentsSettings(
            enabled=True,
            local_tool_output=LocalToolOutputSettings(recent_full_output_count=0),
        ),
        output=OutputSettings(runs_dir=tmp_path / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "1", "name": "appium_source"},
                {"type": "function_call_output", "call_id": "1", "output": "<node>" * 2000},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert "Artifact path:" in filtered.input[1]["output"]
    assert list((tmp_path / "runs" / "run-1" / "artifacts" / "tools").glob("*.json"))
