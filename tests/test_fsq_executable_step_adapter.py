from pathlib import Path

import pytest

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import ConfigurationError, EvidencePolicy


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


def _adapter() -> FsqExecutableStepAdapter:
    return FsqExecutableStepAdapter(registry_snapshot=build_capability_registry().snapshot())


def test_fsq_executable_step_adapter_preserves_order_and_canonical_action_names(tmp_path: Path) -> None:
    case = _load_case(tmp_path)

    steps = _adapter().to_executable_steps(case)

    assert [step.action_name for step in steps] == [
        "launch_app",
        "assert_visible",
        "tap_on",
        "input_text",
        "press_key",
        "assert_state",
        "assert_with_ai",
        "kill_app",
    ]
    assert [step.metadata["authored_action_name"] for step in steps] == [
        "launchApp",
        "assertVisible",
        "tapOn",
        "inputText",
        "pressKey",
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
        "assertion",
        "assertion",
        "teardown",
    ]
    assert steps[0].step_id == "fundamental_test_bing_com_website-step-001"
    assert steps[-1].step_id == "fundamental_test_bing_com_website-step-008"


def test_fsq_executable_step_adapter_normalizes_params_and_source_refs(tmp_path: Path) -> None:
    case = _load_case(tmp_path)

    steps = _adapter().to_executable_steps(case)

    assert steps[0].params == {}
    assert steps[2].params == {"target": "Search box in NTP page"}
    assert steps[3].params == {
        "text": "bing.com",
        "target": "Search box",
        "locator": {"resourceId": "com.microsoft.emmx:id/url_bar"},
    }
    assert steps[3].timeout_ms == 10000
    assert steps[4].params == {"key": "Enter"}

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


def test_fsq_executable_step_adapter_preserves_runtime_secret_refs_and_waits(tmp_path: Path) -> None:
    case_path = tmp_path / "recorded.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Recorded Secret Case
platform: android
---
- inputText:
    text:
      runtimeSecret: TEST_ACCOUNT_PASSWORD
    target: Password field
- waitMs:
    duration_ms: 1
    reason: settle
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    steps = _adapter().to_executable_steps(case)

    assert steps[0].params == {"text": {"runtimeSecret": "TEST_ACCOUNT_PASSWORD"}, "target": "Password field"}
    assert steps[1].action_name == "wait_ms"
    assert steps[1].metadata["authored_action_name"] == "waitMs"
    assert steps[1].params == {"duration_ms": 1, "reason": "settle"}
    assert steps[1].kind == "action"


def test_fsq_executable_step_adapter_applies_default_evidence_policy_except_waits(tmp_path: Path) -> None:
    case_path = tmp_path / "evidence.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Evidence Case
platform: android
---
- launchApp
- waitMs:
    duration_ms: 1
    reason: settle
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)
    policy = EvidencePolicy(capture_after=True, capture_on_failure=True, artifact_kinds=["screenshot"])

    steps = FsqExecutableStepAdapter(default_evidence_policy=policy).to_executable_steps(case)

    assert steps[0].evidence_policy.artifact_kinds == ["screenshot"]
    assert steps[0].evidence_policy is not policy
    assert steps[1].action_name == "waitMs"
    assert steps[1].evidence_policy.artifact_kinds == []


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
        _adapter().to_executable_steps(case)

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
        _adapter().to_executable_steps(case)

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
        _adapter().to_executable_steps(case)

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

    assert _adapter().to_executable_steps(case) == []
