from contextlib import AsyncExitStack
from typing import Any

import pytest

from auto_test_agent.agent import OpenAIAgentsRuntime
from auto_test_agent.config import Settings
from auto_test_agent.models import KnowledgeBundle, MCPToolValidationIssue, OpenAIAgentsSettings, Task


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

    results = await runtime.run_task(task, KnowledgeBundle(), [])

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

    assert "User-provided acceptance criteria: none" in task_input
    assert "Derive acceptance criteria" in task_input


def test_runtime_builds_mcp_validation_diagnostic_steps() -> None:
    settings = Settings(openai_agents=OpenAIAgentsSettings(enabled=True))
    runtime = OpenAIAgentsRuntime(settings, _EmptyToolFactory(), _DiagnosticMCPFactory())

    steps = runtime._build_mcp_validation_steps()

    assert steps[0].status == "skipped"
    assert steps[0].tool_name == "mcp_tool_validation"
    assert "appium-mcp.appium_driver_settings" in steps[0].actual_outcome
    assert steps[0].tool_output["schema_path"] == "$.propertyNames"
