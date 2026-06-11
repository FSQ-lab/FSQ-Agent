from pathlib import Path

import pytest

from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import ConfigurationError


FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Fundamental Test bing.com website
description: Converted from Edge Android Behave BDD scenario.
platform: android
appId: com.microsoft.emmx
tags:
  - p0
  - codex-converted
---
- launchApp
- assertVisible:
    target: New Tab Page account menu
    locator:
      accessibilityId: Account menu
    optional: false
- tapOn:
    target: Search box in NTP page
- inputText:
    text: bing.com
    target: Search box
    locator:
      resourceId: com.microsoft.emmx:id/url_bar
    timeout: 10000
- pressKey:
    key: Enter
- performActions:
    actions: [{"type": "none", "id": "wait-page-load", "actions": [{"type": "pause", "duration": 3000}]}]
- assert:
    element:
      resourceId: com.microsoft.emmx:id/url_bar
    text:
      contains: bing.com
    optional: false
- assertWithAI:
    prompt: Verify Bing page is visible.
    optional: false
- killApp
"""


def _load_case(tmp_path: Path):
    case_path = tmp_path / "fundamental_test_bing_com_website.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    return FsqCaseLoader().load_case(case_path)


def test_fsq_executable_step_adapter_preserves_order_and_action_names(tmp_path: Path) -> None:
    case = _load_case(tmp_path)

    steps = FsqExecutableStepAdapter().to_executable_steps(case)

    assert [step.action_name for step in steps] == [
        "launchApp",
        "assertVisible",
        "tapOn",
        "inputText",
        "pressKey",
        "performActions",
        "assert",
        "assertWithAI",
        "killApp",
    ]
    assert [step.kind for step in steps] == [
        "setup",
        "assertion",
        "action",
        "action",
        "action",
        "action",
        "assertion",
        "assertion",
        "teardown",
    ]
    assert steps[0].step_id == "fundamental_test_bing_com_website-step-001"
    assert steps[-1].step_id == "fundamental_test_bing_com_website-step-009"


def test_fsq_executable_step_adapter_normalizes_params_and_source_refs(tmp_path: Path) -> None:
    case = _load_case(tmp_path)

    steps = FsqExecutableStepAdapter().to_executable_steps(case)

    assert steps[0].params == {}
    assert steps[2].params == {"target": "Search box in NTP page"}
    assert steps[3].params == {
        "text": "bing.com",
        "target": "Search box",
        "locator": {"resourceId": "com.microsoft.emmx:id/url_bar"},
    }
    assert steps[3].timeout_ms == 10000
    assert steps[4].params == {"key": "Enter"}
    assert steps[5].params == {
        "actions": [{"type": "none", "id": "wait-page-load", "actions": [{"type": "pause", "duration": 3000}]}]
    }

    assert steps[1].source_ref is not None
    assert steps[1].source_ref.source_type == "fsq"
    assert steps[1].source_ref.source_id == str(case.path)
    assert steps[1].source_ref.step_index == 1
    assert steps[1].source_ref.metadata == {
        "case_name": "Fundamental Test bing.com website",
        "platform": "android",
    }
    assert steps[1].metadata["case_id"] == "fundamental_test_bing_com_website"
    assert steps[1].metadata["raw_command"] == case.commands[1]


def test_fsq_executable_step_adapter_raises_for_malformed_command(tmp_path: Path) -> None:
    case_path = tmp_path / "bad.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Bad Case
platform: android
---
- tapOn: Login
  inputText: hello
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    with pytest.raises(ConfigurationError) as exc_info:
        FsqExecutableStepAdapter().to_executable_steps(case)

    assert exc_info.value.context["path"] == str(case_path)
    assert exc_info.value.context["step_index"] == 0


def test_fsq_executable_step_adapter_raises_for_invalid_android_payload(tmp_path: Path) -> None:
    case_path = tmp_path / "bad_payload.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Bad Payload
platform: android
---
- tapOn:
    locator:
      unknown: Login
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    with pytest.raises(ConfigurationError) as exc_info:
        FsqExecutableStepAdapter().to_executable_steps(case)

    assert exc_info.value.context["path"] == str(case_path)
    assert exc_info.value.context["step_index"] == 0
    assert exc_info.value.context["action_name"] == "tapOn"
    assert exc_info.value.context["validation_errors"]


def test_fsq_executable_step_adapter_rejects_legacy_scalar_android_payload(tmp_path: Path) -> None:
    case_path = tmp_path / "legacy_scalar.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Legacy Scalar
platform: android
---
- pressKey: Enter
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    with pytest.raises(ConfigurationError) as exc_info:
        FsqExecutableStepAdapter().to_executable_steps(case)

    assert exc_info.value.context["path"] == str(case_path)
    assert exc_info.value.context["step_index"] == 0
    assert exc_info.value.context["action_name"] == "pressKey"
    assert exc_info.value.context["validation_errors"]


def test_fsq_executable_step_adapter_returns_no_steps_for_goal_only_case(tmp_path: Path) -> None:
    case_path = tmp_path / "goal_only.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Goal Only
platform: android
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    assert FsqExecutableStepAdapter().to_executable_steps(case) == []
