from contextlib import AsyncExitStack
import json
from pathlib import Path
from typing import Any

import pytest

from fsq_agent.agent import OpenAIAgentsRuntime
from fsq_agent.agent._prompt import PromptModelBuilder, PromptRenderer
from fsq_agent.agent._verification_task import VerificationEvidenceBuilder
from fsq_agent.config import Settings
from fsq_agent.models import (
    KnowledgeBundle,
    LocalToolOutputSettings,
    MCPToolValidationSettings,
    MCPToolValidationIssue,
    OpenAIAgentsSettings,
    OutputSettings,
    StepResult,
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

    assert "Structured task input:" in task_input
    assert '"schema_version": "task_input_v1"' in task_input
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
    assert "Final output JSON Schema:" in instructions
    assert "AgentFinalOutput" in instructions


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


def test_runtime_instructions_include_knowledge_index_content() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    knowledge = KnowledgeBundle(items={"project.md": "Use Other ways to sign in, then choose password sign-in."})

    instructions = runtime._build_instructions(knowledge, [])

    assert "Private knowledge:" in instructions
    assert "project.md" in instructions
    assert "choose password sign-in" in instructions


def test_prompt_model_builder_and_renderer_use_templates() -> None:
    settings = OpenAIAgentsSettings(enabled=True, prompt={"custom_instructions": ["Custom."]}).prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [])
    task_model = builder.build_task_prompt(Task(id="task-1", description="Do it.", acceptance_criteria=["Done."]))

    assert "Custom operator instructions:" in renderer.render_agent_prompt(agent_model)
    assert "- Custom." in renderer.render_agent_prompt(agent_model)
    assert "Preserve the semantic fidelity of ordered key actions." in renderer.render_agent_prompt(agent_model)
    assert "tool usage error" in renderer.render_agent_prompt(agent_model)
    rendered_task = renderer.render_task_prompt(task_model)
    assert "Structured task input:" in rendered_task
    assert '"id": "task-1"' in rendered_task
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


def test_runtime_mcp_strict_schema_conversion_follows_config() -> None:
    strict_runtime = OpenAIAgentsRuntime(
        Settings(
            openai_agents=OpenAIAgentsSettings(enabled=True),
            mcp_tool_validation=MCPToolValidationSettings(strict_schema=True),
        ),
        _EmptyToolFactory(),
        _FailingMCPFactory(),
    )
    relaxed_runtime = OpenAIAgentsRuntime(
        Settings(
            openai_agents=OpenAIAgentsSettings(enabled=True),
            mcp_tool_validation=MCPToolValidationSettings(strict_schema=False),
        ),
        _EmptyToolFactory(),
        _FailingMCPFactory(),
    )

    assert strict_runtime._build_mcp_config() == {"convert_schemas_to_strict": True}
    assert relaxed_runtime._build_mcp_config() == {"convert_schemas_to_strict": False}


def test_verification_evidence_builder_uses_text_only_after_runner_visual_assertion(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    screenshots_dir = output_root / "appium-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    task = Task(
        id="visual",
        description="Verify the page visually.",
        acceptance_criteria=["Key action 1: assertWithAI Verify the logo is visible."],
    )
    results = [
        StepResult(
            step_id=1,
            status="success",
            actual_outcome=json.dumps(
                {
                    "schema_version": "task_run_v1",
                    "status": "success",
                    "summary": "Visual assertion passed.",
                    "pre_plan": [],
                    "plan_updates": [],
                    "satisfied_criteria": ["Key action 1: assertWithAI Verify the logo is visible."],
                    "unmet_criteria": [],
                    "evidence": [f"Runner inspected submitted screenshot {screenshot_path} and verified the logo."],
                    "errors": [],
                }
            ),
            tool_name="openai_agents.runner",
        )
    ]

    model_input = VerificationEvidenceBuilder().build_model_input(task, results, image_root=output_root)

    assert isinstance(model_input, str)
    evidence = json.loads(model_input)
    assert evidence["verification_mode"] == "normal"
    assert evidence["blocking_criteria"][0]["text"] == "Key action 1: assertWithAI Verify the logo is visible."
    assert "visual_artifacts" not in evidence
    assert evidence["agent_claims"]["status"] == "success"
    assert "Runner inspected submitted screenshot" in evidence["agent_claims"]["evidence"][0]
    assert "input_image" not in model_input


def test_verification_evidence_builder_does_not_attach_images_from_paths(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    screenshot_path = outside_root / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    task = Task(id="visual", description="Verify the page visually.")
    results = [
        StepResult(
            step_id=1,
            status="success",
            actual_outcome=f"Screenshot outside output root: {screenshot_path}",
        )
    ]

    model_input = VerificationEvidenceBuilder().build_model_input(task, results, image_root=output_root)

    assert isinstance(model_input, str)
    assert "input_image" not in model_input
    assert "visual_artifacts" not in model_input


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


def test_runtime_input_filter_leaves_plain_screenshot_outputs_text_only(tmp_path: Path) -> None:
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

    output_root = tmp_path / "output"
    screenshots_dir = output_root / "appium-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(enabled=True),
        output=OutputSettings(root_dir=output_root, runs_dir=output_root / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "img", "name": "appium_screenshot"},
                {
                    "type": "function_call_output",
                    "call_id": "img",
                    "output": f"Screenshot saved successfully to: {screenshot_path}",
                },
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input == data.model_data.input


def test_runtime_input_filter_attaches_submitted_visual_assertion_image(tmp_path: Path) -> None:
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

    output_root = tmp_path / "output"
    screenshots_dir = output_root / "appium-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(enabled=True),
        output=OutputSettings(root_dir=output_root, runs_dir=output_root / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    output = json.dumps(
        {
            "type": "visual_assertion_submission",
            "assertion_id": "key-action-7",
            "prompt": "Verify the logo is visible.",
            "screenshot_path": str(screenshot_path),
        }
    )
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "visual", "name": "submit_visual_assertion"},
                {"type": "function_call_output", "call_id": "visual", "output": output},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input[1]["output"] == output
    image_message = filtered.input[2]
    assert image_message["role"] == "user"
    assert image_message["content"][0]["type"] == "input_text"
    assert "key-action-7" in image_message["content"][0]["text"]
    assert "Verify the logo is visible." in image_message["content"][0]["text"]
    assert str(screenshot_path.resolve()) in image_message["content"][0]["text"]
    assert image_message["content"][1]["type"] == "input_image"
    assert image_message["content"][1]["image_url"].startswith("data:image/png;base64,")


def test_runtime_input_filter_rejects_screenshot_images_outside_output_root(tmp_path: Path) -> None:
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

    output_root = tmp_path / "output"
    output_root.mkdir()
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    screenshot_path = outside_root / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(enabled=True),
        output=OutputSettings(root_dir=output_root, runs_dir=output_root / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _FailingMCPFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "visual", "name": "submit_visual_assertion"},
                {
                    "type": "function_call_output",
                    "call_id": "visual",
                    "output": json.dumps(
                        {
                            "type": "visual_assertion_submission",
                            "assertion_id": "key-action-7",
                            "prompt": "Verify the logo is visible.",
                            "screenshot_path": str(screenshot_path),
                        }
                    ),
                },
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert filtered.input == data.model_data.input
