import asyncio
import json
from pathlib import Path
import time
from typing import Any

import pytest

from fsq_agent.agent import OpenAIAgentsRuntime
from fsq_agent.agent._harness_tools import HarnessToolAdapter
from fsq_agent.agent._prompt import PromptModelBuilder, PromptRenderer
from fsq_agent.agent._verification_task import VerificationEvidenceBuilder
from fsq_agent.config import Settings
from fsq_agent.models import (
    AgentFinalOutput,
    HarnessActionResult,
    HarnessContext,
    HarnessFunctionSchema,
    KnowledgeBundle,
    LocalToolOutputSettings,
    OpenAIAgentsSettings,
    OutputSettings,
    RuntimeSecretSettings,
    StepResult,
    Task,
)
from fsq_agent.providers import build_model_provider_session


class _EmptyToolFactory:
    def build_tools(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        return []


class _FakeFunctionTool:
    def __init__(self, **kwargs: Any) -> None:
        self.name = kwargs["name"]
        self.description = kwargs["description"]
        self.params_json_schema = kwargs["params_json_schema"]
        self.on_invoke_tool = kwargs["on_invoke_tool"]


class _FakeHarness:
    def __init__(self) -> None:
        self.steps: list[Any] = []

    def action_space(self) -> list[HarnessFunctionSchema]:
        return [
            HarnessFunctionSchema(
                name="tap_on",
                description="Tap an Android UI target.",
                params_json_schema={"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]},
                platform="android",
                driver_method="tap_on",
                fsq_action_name="tapOn",
            )
        ]

    def get_context(self) -> HarnessContext:
        return HarnessContext(platform="android", session_id="session-1")

    def invoke_action(self, step: Any, context: HarnessContext) -> HarnessActionResult:
        self.steps.append(step)
        return HarnessActionResult(
            status="passed",
            action_name=step.action_name,
            output={"context_session_id": context.session_id, "params": step.params},
        )


class _FailingHarness(_FakeHarness):
    def action_space(self) -> list[HarnessFunctionSchema]:
        raise RuntimeError("Harness action-space failed")


def _fake_harness_factory(_run_id: str) -> _FakeHarness:
    return _FakeHarness()


class _FakeProviderSession:
    def create_agents_provider(self, **_kwargs: Any) -> str:
        return "provider"

    async def close(self) -> None:
        return None


class _FakeAgent:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeRunConfig:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeToolOutputTrimmer:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeRunResult:
    final_output = AgentFinalOutput(status="success", summary="Done.")

    async def stream_events(self) -> Any:
        if False:
            yield None


class _FakeRunner:
    @staticmethod
    def run_streamed(*_args: Any, **_kwargs: Any) -> _FakeRunResult:
        return _FakeRunResult()


def _patch_runtime_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    import agents
    import agents.extensions
    import fsq_agent.agent._openai_runtime as runtime_module

    monkeypatch.setattr(runtime_module, "build_model_provider_session", lambda _settings: _FakeProviderSession())
    monkeypatch.setattr(agents, "Agent", _FakeAgent)
    monkeypatch.setattr(agents, "FunctionTool", _FakeFunctionTool)
    monkeypatch.setattr(agents, "RunConfig", _FakeRunConfig)
    monkeypatch.setattr(agents, "Runner", _FakeRunner)
    monkeypatch.setattr(agents, "set_tracing_disabled", lambda _disabled: None)
    monkeypatch.setattr(agents.extensions, "ToolOutputTrimmer", _FakeToolOutputTrimmer)


@pytest.mark.asyncio
async def test_runtime_failure_returns_failed_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), lambda _run_id: _FailingHarness())
    task = Task(
        id="runtime-failure",
        name="Runtime Failure",
        description="Trigger harness failure.",
        acceptance_criteria=["A failed step is returned."],
    )

    results = await runtime.run_task(task, KnowledgeBundle(), [], "runtime-failure-2026-05-09_00-00-00")

    assert results[0].status == "failed"
    assert results[0].tool_name == "openai_agents.runner"
    assert "Harness action-space discovery failed" in str(results[0].error)


@pytest.mark.asyncio
async def test_runtime_emits_startup_events_before_main_planning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), _fake_harness_factory)
    task = Task(id="startup", name="Startup", description="Run startup.")
    events: list[Any] = []

    results = await runtime.run_task(task, KnowledgeBundle(), [], "startup-run", event_sink=events.append)

    assert results[-1].status == "success"
    titles = [event.title for event in events]
    expected_titles = [
        "Runtime startup started",
        "Provider setup started",
        "Provider setup completed",
        "Harness setup started",
        "Harness setup completed",
        "Tool setup started",
        "Tool setup completed",
        "SDK agent ready",
        "Planning started",
    ]
    for title in expected_titles:
        assert title in titles
    assert [titles.index(title) for title in expected_titles] == sorted(titles.index(title) for title in expected_titles)
    harness_started = events[titles.index("Harness setup started")]
    assert harness_started.payload["timeout_seconds"] == 60
    assert harness_started.payload["app_id_configured"] is False
    harness_completed = events[titles.index("Harness setup completed")]
    assert harness_completed.payload["harness_class"] == "_FakeHarness"
    assert "driver_class" not in harness_completed.payload


@pytest.mark.asyncio
async def test_runtime_harness_construction_failure_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)

    def fail_harness(_run_id: str) -> _FakeHarness:
        raise RuntimeError("device connect failed")

    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), fail_harness)
    events: list[Any] = []

    results = await runtime.run_task(Task(id="failure", description="Fail startup."), KnowledgeBundle(), [], "failure-run", events.append)

    assert results[0].status == "failed"
    assert "device connect failed" in str(results[0].error)
    titles = [event.title for event in events]
    assert "Harness setup started" in titles
    assert "Harness setup completed" not in titles
    assert titles[-1] == "SDK run failed"


@pytest.mark.asyncio
async def test_runtime_harness_construction_timeout_is_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    _patch_runtime_sdk(monkeypatch)

    def slow_harness(_run_id: str) -> _FakeHarness:
        time.sleep(2)
        return _FakeHarness()

    settings = Settings(agent={"step_timeout_seconds": 1}, openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), slow_harness)
    events: list[Any] = []

    results = await runtime.run_task(Task(id="timeout", description="Timeout startup."), KnowledgeBundle(), [], "timeout-run", events.append)

    assert results[0].status == "failed"
    assert "Harness setup timed out after 1 seconds" in str(results[0].error)
    titles = [event.title for event in events]
    assert "Harness setup started" in titles
    assert "Harness setup completed" not in titles
    assert titles[-1] == "SDK run failed"


def test_runtime_harness_timeout_does_not_wait_for_worker_shutdown() -> None:
    def slow_harness(_run_id: str) -> _FakeHarness:
        time.sleep(3)
        return _FakeHarness()

    settings = Settings(agent={"step_timeout_seconds": 1}, openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), slow_harness)

    async def run_timeout() -> None:
        with pytest.raises(TimeoutError, match="Harness setup timed out after 1 seconds"):
            await runtime._build_harness_with_timeout("shutdown-run")

    started = time.perf_counter()
    asyncio.run(run_timeout())

    assert time.perf_counter() - started < 1.8


def test_runtime_builds_step_results_from_structured_pre_plan() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
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


def test_runtime_task_input_uses_goal_only_verification_contract() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    task = Task(id="derive", name="Derive", description="Open the page and verify it loads.")

    task_input = runtime._build_task_input(task)

    assert "Structured task input:" in task_input
    assert '"schema_version": "task_input_v1"' in task_input
    assert "Final verification goal: none provided" in task_input
    assert "verification_goal" in task_input


def test_runtime_instructions_include_custom_operator_instructions() -> None:
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(
            prompt={"custom_instructions": ["Prefer accessibility locators before coordinate-based actions."]},
        )
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

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
        "{% for item in private_knowledge %}- {{ item.key }}={{ item.value }}\n{% endfor %}",
        encoding="utf-8",
    )
    task_template.write_text(
        "Task {{ task.id }}: {{ task.description }}\n"
        "{% if task.acceptance_criteria %}{{ task.acceptance_criteria | join(', ') }}{% else %}Configured no criteria text.{% endif %}\n",
        encoding="utf-8",
    )
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(
            prompt={
                "agent_template_path": agent_template,
                "task_template_path": task_template,
            },
        )
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    knowledge = KnowledgeBundle(items={"k": "v"})

    instructions = runtime._build_instructions(knowledge, [])
    task_input = runtime._build_task_input(Task(id="t1", description="Do it."))

    assert instructions.startswith("Configured base instruction.")
    assert "Configured knowledge:" in instructions
    assert task_input == "Task t1: Do it.\nConfigured no criteria text."


def test_runtime_instructions_include_knowledge_index_content() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    knowledge = KnowledgeBundle(items={"project.md": "Use Other ways to sign in, then choose password sign-in."})

    instructions = runtime._build_instructions(knowledge, [])

    assert "Private knowledge:" in instructions
    assert "project.md" in instructions
    assert "choose password sign-in" in instructions


def test_prompt_model_builder_and_renderer_use_templates() -> None:
    settings = OpenAIAgentsSettings(prompt={"custom_instructions": ["Custom."]}).prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [])
    task_model = builder.build_task_prompt(Task(id="task-1", description="Do it.", verification_goal="Done."))

    assert "Custom operator instructions:" in renderer.render_agent_prompt(agent_model)
    assert "- Custom." in renderer.render_agent_prompt(agent_model)
    assert "Preserve the semantic fidelity of ordered key actions." in renderer.render_agent_prompt(agent_model)
    assert "tool usage error" in renderer.render_agent_prompt(agent_model)
    rendered_task = renderer.render_task_prompt(task_model)
    assert "Structured task input:" in rendered_task
    assert '"id": "task-1"' in rendered_task
    assert "Final verification goal:" in rendered_task
    assert "Done." in rendered_task


def test_prompt_model_builder_loads_custom_instructions_file(tmp_path: Path) -> None:
    custom_instructions = tmp_path / "custom-instructions.md"
    custom_instructions.write_text("First instruction.\n\nSecond instruction.", encoding="utf-8")
    settings = OpenAIAgentsSettings(prompt={"custom_instructions_path": custom_instructions}).prompt
    builder = PromptModelBuilder(settings)
    renderer = PromptRenderer(settings)

    agent_model = builder.build_agent_prompt(KnowledgeBundle(), [])
    rendered = renderer.render_agent_prompt(agent_model)

    assert "- First instruction." in rendered
    assert "- Second instruction." in rendered


def test_prompt_renderer_injects_model_into_configured_jinja_templates(tmp_path: Path) -> None:
    agent_template = tmp_path / "agent.j2"
    task_template = tmp_path / "task.j2"
    agent_template.write_text("{{ variables.prefix }}{% for instruction in custom_instructions %} {{ instruction }}{% endfor %}", encoding="utf-8")
    task_template.write_text("Task {{ task.id }} {{ task.variables.prefix }}", encoding="utf-8")
    settings = OpenAIAgentsSettings(
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


@pytest.mark.asyncio
async def test_harness_tool_adapter_invokes_harness_action() -> None:
    harness = _FakeHarness()
    adapter = HarnessToolAdapter(harness)

    tools = adapter.build_tools(_FakeFunctionTool)
    output = await tools[0].on_invoke_tool(None, json.dumps({"target": "Downloads"}))

    payload = json.loads(output)
    assert tools[0].name == "tap_on"
    assert payload["tool_origin"] == "harness"
    assert payload["status"] == "passed"
    assert payload["driver_method"] == "tap_on"
    assert payload["fsq_action_name"] == "tapOn"
    assert payload["result"]["output"]["params"] == {"target": "Downloads"}
    assert harness.steps[0].action_name == "tapOn"
    assert harness.steps[0].kind == "action"


def test_runtime_tool_origin_recognizes_harness_tools() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory(), _fake_harness_factory)
    runtime._harness_tool_names = {"tap_on"}

    assert runtime._tool_origin("tap_on") == "harness"
    assert runtime._tool_origin("read_file") == "common"
    assert runtime._tool_origin("read_knowledge_index") == "runtime"
    assert runtime._tool_origin("unexpected_tool") == "unknown"


def test_verification_evidence_builder_uses_text_only_after_runner_visual_assertion(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    screenshots_dir = output_root / "harness-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    task = Task(
        id="visual",
        description="Verify the page visually.",
        verification_goal="Verify the logo is visible.",
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
    assert evidence["verification_goal"] == "Verify the logo is visible."
    assert "verification_mode" not in evidence
    assert "blocking_criteria" not in evidence
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

    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())

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


def test_provider_session_builds_azure_openai_agents_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class _AsyncOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    class _OpenAIProvider:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
    settings = Settings(openai_agents=OpenAIAgentsSettings())

    session = build_model_provider_session(settings)
    provider = session.create_agents_provider(openai_provider_type=_OpenAIProvider, async_openai_type=_AsyncOpenAI)

    assert provider.kwargs["use_responses"] is True
    assert provider.kwargs["openai_client"].kwargs == {
        "api_key": "azure-key",
        "base_url": "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/",
        "default_headers": None,
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

    settings = Settings(openai_agents=OpenAIAgentsSettings())
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
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
            local_tool_output=LocalToolOutputSettings(recent_full_output_count=0),
        ),
        output=OutputSettings(runs_dir=tmp_path / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "1", "name": "harness_source"},
                {"type": "function_call_output", "call_id": "1", "output": "<node>" * 2000},
            ],
            instructions="instructions",
        )
    )

    filtered = input_filter(data)

    assert "Artifact path:" in filtered.input[1]["output"]
    assert list((tmp_path / "runs" / "run-1" / "artifacts" / "tools").glob("*.json"))


def test_runtime_preview_redacts_wrapped_sensitive_tool_output() -> None:
    runtime = OpenAIAgentsRuntime(Settings(openai_agents=OpenAIAgentsSettings()), _EmptyToolFactory())
    output = json.dumps(
        {
            "tool_name": "get_runtime_secret",
            "model_output": "full",
            "result": {
                "tool_name": "get_runtime_secret",
                "status": "success",
                "output": {
                    "type": "runtime_secret",
                    "name": "TEST_ACCOUNT_PASSWORD",
                    "value": "super-secret",
                    "sensitive": True,
                },
                "sensitive": True,
            },
        }
    )

    preview = runtime._preview(output)

    assert "super-secret" not in preview
    assert '"value": "***"' in preview


def test_runtime_redacts_configured_secret_values_from_final_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "super-secret")
    runtime = OpenAIAgentsRuntime(
        Settings(
            openai_agents=OpenAIAgentsSettings(),
            runtime_secrets=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
        ),
        _EmptyToolFactory(),
    )
    final_output = AgentFinalOutput(
        status="success",
        summary="Logged in with super-secret.",
        evidence=["The password super-secret was entered."],
    )

    redacted = runtime._redact_runtime_secrets(final_output)

    assert isinstance(redacted, AgentFinalOutput)
    assert redacted.summary == "Logged in with ***."
    assert redacted.evidence == ["The password *** was entered."]


def test_runtime_redacts_configured_secret_values_from_tool_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "super-secret")
    runtime = OpenAIAgentsRuntime(
        Settings(
            openai_agents=OpenAIAgentsSettings(),
            runtime_secrets=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]),
        ),
        _EmptyToolFactory(),
    )
    item = type("Item", (), {"raw_item": {"arguments": {"text": "super-secret", "target": "Password"}}})()

    arguments = runtime._tool_arguments(item)

    assert arguments == {"text": "***", "target": "Password"}


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
    screenshots_dir = output_root / "harness-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(),
        output=OutputSettings(root_dir=output_root, runs_dir=output_root / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
    input_filter = runtime._build_run_config(_RunConfig, _ToolOutputTrimmer, provider="provider", run_id="run-1").kwargs[
        "call_model_input_filter"
    ]
    data = SimpleNamespace(
        model_data=ModelInputData(
            input=[
                {"type": "function_call", "call_id": "img", "name": "harness_screenshot"},
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


def test_runtime_input_filter_does_not_attach_submitted_visual_assertion_image(tmp_path: Path) -> None:
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
    screenshots_dir = output_root / "harness-screenshots"
    screenshots_dir.mkdir(parents=True)
    screenshot_path = screenshots_dir / "screenshot.png"
    screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    settings = Settings(
        openai_agents=OpenAIAgentsSettings(),
        output=OutputSettings(root_dir=output_root, runs_dir=output_root / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
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
    assert len(filtered.input) == 2


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
        openai_agents=OpenAIAgentsSettings(),
        output=OutputSettings(root_dir=output_root, runs_dir=output_root / "runs"),
    )
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory())
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
