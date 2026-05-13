from pathlib import Path

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


def _write_event(events_path: Path, **event: object) -> None:
    import json

    base = {
        "run_id": "run-1",
        "task_id": "task-1",
        "type": "tool_call_completed",
        "title": "Tool call completed",
        "sequence": 1,
        "message": "Tool returned output.",
        "tool_name": None,
        "tool_call_id": None,
        "tool_arguments": None,
        "tool_output_preview": None,
        "duration_ms": None,
        "payload": {},
    }
    base.update(event)
    with events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(base, ensure_ascii=False) + "\n")


def _write_tool_call(events_path: Path, call_id: str, tool_name: str, arguments: dict[str, object], output: str, *, failed: bool = False) -> None:
    _write_event(
        events_path,
        type="tool_call_started",
        title="Tool call started",
        sequence=len(events_path.read_text(encoding="utf-8").splitlines()) + 1 if events_path.exists() else 1,
        message=f"Calling {tool_name}.",
        tool_name=tool_name,
        tool_call_id=call_id,
        tool_arguments=arguments,
    )
    _write_event(
        events_path,
        type="tool_call_failed" if failed else "tool_call_completed",
        title="Tool call failed" if failed else "Tool call completed",
        sequence=len(events_path.read_text(encoding="utf-8").splitlines()) + 1,
        message=output,
        tool_call_id=call_id,
        tool_output_preview=output,
    )


@pytest.mark.asyncio
async def test_verifier_independently_verifies_appium_events_after_invalid_runner_output(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    task = Task(
        id="appium",
        name="Appium",
        description="Run appium case.",
        acceptance_criteria=[
            "Key action 1: assertVisible New Tab Page account menu (locator: accessibilityId=Account menu)",
            "Key action 2: tapOn Search box (locator: resourceId=com.microsoft.emmx:id/search_box_text)",
            "Key action 3: inputText https://www.google.com into Search box (locator: resourceId=com.microsoft.emmx:id/url_bar)",
            "Key action 4: pressKey: Enter",
            "Key action 5: assert {'contains': '1'} (element: resourceId=android:id/text1; text: {\"contains\": \"1\"})",
        ],
    )

    _write_tool_call(events_path, "find-account", "appium_find_element", {"strategy": "accessibility id", "selector": "Account menu"}, "elementId:account\nSuccessfully found element Account menu with strategy accessibility id.")
    _write_tool_call(events_path, "find-search", "appium_find_element", {"strategy": "id", "selector": "com.microsoft.emmx:id/search_box_text"}, "elementId:search\nSuccessfully found element com.microsoft.emmx:id/search_box_text with strategy id.")
    _write_tool_call(events_path, "tap-search", "appium_gesture", {"action": "tap", "elementUUID": "search"}, "elementId:search\nSuccessfully tapped element search.")
    _write_tool_call(events_path, "find-url", "appium_find_element", {"strategy": "id", "selector": "com.microsoft.emmx:id/url_bar"}, "elementId:url\nSuccessfully found element com.microsoft.emmx:id/url_bar with strategy id.")
    _write_tool_call(events_path, "set-url", "appium_set_value", {"elementUUID": "url", "text": "https://www.google.com"}, "elementId:url\nSuccessfully set value https://www.google.com into element url.")
    _write_tool_call(events_path, "press-enter", "appium_mobile_press_key", {"key": "ENTER"}, "Successfully pressed key \"ENTER\" on Android.")
    _write_tool_call(events_path, "find-count", "appium_find_element", {"strategy": "id", "selector": "android:id/text1"}, "elementId:count\nSuccessfully found element android:id/text1 with strategy id.")
    _write_tool_call(events_path, "read-count", "appium_get_text", {"elementUUID": "count"}, "elementId:count\nSuccessfully got text 1 from element count.")

    result = await Verifier().verify(
        task,
        [StepResult(step_id=1, status="failed", actual_outcome="content filter", tool_name="openai_agents.runner")],
        events_path=events_path,
    )

    assert result.status == "success"
    assert result.unmet_criteria == []
    assert result.satisfied_criteria == task.acceptance_criteria


@pytest.mark.asyncio
async def test_verifier_flags_conflicting_appium_key_identity(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    task = Task(
        id="appium",
        name="Appium",
        description="Run appium case.",
        acceptance_criteria=["Key action 1: pressKey: Enter"],
    )
    _write_tool_call(
        events_path,
        "press-enter",
        "appium_mobile_press_key",
        {"key": "BACK", "keyCode": 66},
        "Successfully pressed key \"BACK\" on Android.",
    )

    result = await Verifier().verify(
        task,
        [StepResult(step_id=1, status="failed", actual_outcome="content filter", tool_name="openai_agents.runner")],
        events_path=events_path,
    )

    assert result.status == "inconclusive"
    assert result.unmet_criteria == task.acceptance_criteria
    assert any("conflicting key identities" in diagnostic for diagnostic in result.diagnostics)