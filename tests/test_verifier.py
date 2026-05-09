import pytest

from fsq_agent.agent import Verifier
from fsq_agent.models import StepResult, Task


def _task() -> Task:
    return Task(
        id="verify-1",
        name="Verify structured result",
        description="Complete a task.",
        acceptance_criteria=["Criterion A", "Criterion B"],
    )


@pytest.mark.asyncio
async def test_verifier_accepts_structured_success() -> None:
    result = await Verifier().verify(
        _task(),
        [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Done","pre_plan":[],"plan_updates":[],"satisfied_criteria":["Criterion A","Criterion B"],"unmet_criteria":[],"evidence":["Observed A and B"],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ],
    )

    assert result.status == "success"
    assert result.satisfied_criteria == ["Criterion A", "Criterion B"]
    assert result.unmet_criteria == []
    assert result.diagnostics == ["Observed A and B"]


@pytest.mark.asyncio
async def test_verifier_downgrades_success_with_unmet_criteria() -> None:
    result = await Verifier().verify(
        _task(),
        [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Partial","pre_plan":[],"plan_updates":[],"satisfied_criteria":["Criterion A"],"unmet_criteria":["Criterion B"],"evidence":[],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ],
    )

    assert result.status == "inconclusive"
    assert result.unmet_criteria == ["Criterion B"]


@pytest.mark.asyncio
async def test_verifier_downgrades_success_when_acceptance_criterion_is_not_reported() -> None:
    result = await Verifier().verify(
        _task(),
        [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Partial","pre_plan":[],"plan_updates":[],"satisfied_criteria":["Criterion A"],"unmet_criteria":[],"evidence":["Observed A"],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ],
    )

    assert result.status == "inconclusive"
    assert result.unmet_criteria == ["Criterion B"]


@pytest.mark.asyncio
async def test_verifier_uses_structured_sdk_unmet_criteria_when_pre_plan_step_failed() -> None:
    result = await Verifier().verify(
        _task(),
        [
            StepResult(
                step_id=1,
                status="failed",
                actual_outcome="Action: Complete criterion B.\nSuccess criteria:\n- Criterion B",
                tool_name="pre_plan",
            ),
            StepResult(
                step_id=2,
                status="success",
                actual_outcome='{"status":"failed","summary":"Only B failed","pre_plan":[],"plan_updates":["B tool failed"],"satisfied_criteria":["Criterion A"],"unmet_criteria":["Criterion B"],"evidence":["Observed A"],"errors":["B failed"]}',
                tool_name="openai_agents.runner",
            ),
        ],
    )

    assert result.status == "failed"
    assert result.satisfied_criteria == ["Criterion A"]
    assert result.unmet_criteria == ["Criterion B"]
    assert result.diagnostics == ["Observed A", "B tool failed", "B failed"]


@pytest.mark.asyncio
async def test_verifier_downgrades_structured_success_when_execution_step_failed() -> None:
    result = await Verifier().verify(
        _task(),
        [
            StepResult(
                step_id=1,
                status="failed",
                actual_outcome="A recovery step failed.",
                tool_name="pre_plan",
            ),
            StepResult(
                step_id=2,
                status="success",
                actual_outcome='{"status":"success","summary":"Done","pre_plan":[],"plan_updates":[],"satisfied_criteria":["Criterion A","Criterion B"],"unmet_criteria":[],"evidence":["Observed A and B"],"errors":[]}',
                tool_name="openai_agents.runner",
            ),
        ],
    )

    assert result.status == "inconclusive"
    assert result.satisfied_criteria == ["Criterion A", "Criterion B"]
    assert result.unmet_criteria == []
    assert "Success was downgraded" in result.summary
    assert "A recovery step failed." in result.diagnostics


@pytest.mark.asyncio
async def test_verifier_marks_non_json_output_inconclusive() -> None:
    result = await Verifier().verify(
        _task(),
        [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome="I think it worked.",
                tool_name="openai_agents.runner",
            )
        ],
    )

    assert result.status == "inconclusive"
    assert result.unmet_criteria == ["Criterion A", "Criterion B"]


@pytest.mark.asyncio
async def test_verifier_accepts_agent_derived_criteria_when_task_has_none() -> None:
    task = Task(id="derive-1", name="Derived", description="Open a page.")

    result = await Verifier().verify(
        task,
        [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Done","pre_plan":[],"plan_updates":[],"satisfied_criteria":["The task flow completed successfully."],"unmet_criteria":[],"evidence":["Flow completed"],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ],
    )

    assert result.status == "success"
    assert result.satisfied_criteria == ["The task flow completed successfully."]


@pytest.mark.asyncio
async def test_verifier_downgrades_success_without_provided_or_derived_criteria() -> None:
    task = Task(id="derive-2", name="Derived", description="Do it.")

    result = await Verifier().verify(
        task,
        [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Done","pre_plan":[],"plan_updates":[],"satisfied_criteria":[],"unmet_criteria":[],"evidence":[],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ],
    )

    assert result.status == "inconclusive"
    assert result.unmet_criteria == ["No acceptance criteria were provided by the user or derived by the agent."]