from pathlib import Path

import pytest

from fsq_agent.cli._task_loader import load_task, load_tasks
from fsq_agent.fsq import FsqCaseLoader, FsqTaskAdapter
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
    locator:
      resourceId: com.microsoft.emmx:id/search_box_text
- inputText:
    text: bing.com
    target: Search box
    locator:
      resourceId: com.microsoft.emmx:id/url_bar
- pressKey: Enter
- assertWithAI:
    prompt: Analyze the screenshot to verify bing webpage displayed normally.
    optional: false
- killApp
"""


def test_fsq_case_loader_loads_two_document_case(tmp_path: Path) -> None:
    case_path = tmp_path / "fundamental_test_bing_com_website.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")

    case = FsqCaseLoader().load_case(case_path)

    assert case.config.schema_version == "fsq.ai-test/v1"
    assert case.config.name == "Fundamental Test bing.com website"
    assert case.config.platform == "android"
    assert case.config.app_id == "com.microsoft.emmx"
    assert len(case.commands) == 7


def test_fsq_task_adapter_renders_case_as_advisory_description(tmp_path: Path) -> None:
    case_path = tmp_path / "fundamental_test_bing_com_website.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    case = FsqCaseLoader().load_case(case_path)

    task = FsqTaskAdapter().to_task(case)

    assert task.id == "fundamental_test_bing_com_website"
    assert task.name == "Fundamental Test bing.com website"
    assert task.key_actions == [
        "Key action 1: assertVisible New Tab Page account menu (locator: accessibilityId=Account menu)",
        "Key action 2: tapOn Search box in NTP page (locator: resourceId=com.microsoft.emmx:id/search_box_text)",
        "Key action 3: inputText bing.com into Search box (locator: resourceId=com.microsoft.emmx:id/url_bar)",
        "Key action 4: pressKey: Enter",
        "Key action 5: assertWithAI Analyze the screenshot to verify bing webpage displayed normally.",
    ]
    assert [criterion.kind for criterion in task.verification_criteria] == [
        "goal",
        "assertion",
        "operation",
        "operation",
        "operation",
        "assertion",
    ]
    assert task.verification_goal == "Goal completed: Fundamental Test bing.com website"
    assert "advisory for execution details" in task.description
    assert "Ordered key actions for execution" in task.description
    assert "Final verification criteria" in task.description
    assert "App ID: com.microsoft.emmx" in task.description
    assert "assertWithAI" in task.description
    assert "resourceId" in task.description


def test_fsq_task_adapter_skips_optional_and_setup_teardown_key_actions(tmp_path: Path) -> None:
    case_path = tmp_path / "optional_case.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Optional Case
platform: android
---
- launchApp
- assertVisible:
    target: Optional promo
    locator:
      text: Promo
    optional: true
- tapOn:
    target: Required button
    locator:
      accessibilityId: Required
- killApp
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    task = FsqTaskAdapter().to_task(case)

    assert task.key_actions == [
        "Key action 1: tapOn Required button (locator: accessibilityId=Required)",
    ]
    assert [criterion.text for criterion in task.verification_criteria] == [
        "Goal completed: Optional Case",
        "Key action 1: tapOn Required button (locator: accessibilityId=Required)",
    ]
    assert [criterion.kind for criterion in task.verification_criteria] == ["goal", "operation"]


def test_fsq_task_adapter_renders_msa_precondition_without_secret_values(tmp_path: Path) -> None:
    case_path = tmp_path / "rewards.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Rewards Case
description: This case assumes the test device is already signed in with MSA.
platform: android
tags:
  - requires-msa
---
- launchApp
- assertVisible:
    target: Signed-in account entry
    locator:
      resourceId: com.microsoft.emmx:id/edge_account_image_view
    optional: false
- killApp
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    task = FsqTaskAdapter().to_task(case)

    assert "Inferred preconditions" in task.description
    assert "Microsoft account sign-in is required" in task.description
    assert "get_runtime_secret" in task.description
    assert "TEST_ACCOUNT_EMAIL" in task.description
    assert "TEST_ACCOUNT_PASSWORD" in task.description
    assert "mobiletest0002" not in task.description
    assert "Edge_Mobile_0002@outlook.com" not in task.description


def test_fsq_task_adapter_falls_back_to_goal_when_no_key_actions(tmp_path: Path) -> None:
    case_path = tmp_path / "goal_only.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Goal Only Case
platform: android
---
- launchApp
- killApp
""",
        encoding="utf-8",
    )
    case = FsqCaseLoader().load_case(case_path)

    task = FsqTaskAdapter().to_task(case)

    assert task.key_actions == []
    assert task.acceptance_criteria == ["Goal completed: Goal Only Case"]
    assert [criterion.kind for criterion in task.verification_criteria] == ["goal"]


def test_fsq_case_loader_accepts_single_document_goal_only_case(tmp_path: Path) -> None:
    case_path = tmp_path / "single_doc_goal.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Single Document Goal
platform: android
""",
        encoding="utf-8",
    )

    case = FsqCaseLoader().load_case(case_path)
    task = FsqTaskAdapter().to_task(case)

    assert case.commands == []
    assert task.key_actions == []
    assert task.verification_goal == "Goal completed: Single Document Goal"


def test_fsq_case_loader_accepts_empty_command_document_goal_only_case(tmp_path: Path) -> None:
    case_path = tmp_path / "empty_commands_goal.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Empty Commands Goal
platform: android
---
[]
""",
        encoding="utf-8",
    )

    case = FsqCaseLoader().load_case(case_path)

    assert case.commands == []


def test_load_task_detects_fsq_codex_yaml(tmp_path: Path) -> None:
    case_path = tmp_path / "case.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")

    task = load_task(case_path)

    assert task.name == "Fundamental Test bing.com website"
    assert task.key_actions[0].startswith("Key action 1:")
    assert "Reference FSQ command flow" in task.description


def test_load_tasks_prefers_recursive_fsq_cases(tmp_path: Path) -> None:
    area = tmp_path / "android" / "rendering"
    area.mkdir(parents=True)
    (area / "case.codex.yaml").write_text(FSQ_CASE, encoding="utf-8")
    (tmp_path / "legacy.yaml").write_text("description: legacy\n", encoding="utf-8")

    tasks = load_tasks(tmp_path)

    assert [task.name for task in tasks] == ["Fundamental Test bing.com website"]


def test_load_task_rejects_non_fsq_task_file(tmp_path: Path) -> None:
    task_path = tmp_path / "task.json"
    task_path.write_text('{"description":"legacy"}\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="FSQ .codex.yaml"):
        load_task(task_path)


def test_fsq_case_loader_rejects_too_many_documents(tmp_path: Path) -> None:
    case_path = tmp_path / "bad.codex.yaml"
    case_path.write_text(
        "schemaVersion: fsq.ai-test/v1\nname: Bad\nplatform: android\n---\n[]\n---\nextra: true\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="Invalid FSQ case file"):
        FsqCaseLoader().load_case(case_path)
