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
    assert task.acceptance_criteria == []
    assert "advisory for execution details" in task.description
    assert "App ID: com.microsoft.emmx" in task.description
    assert "assertWithAI" in task.description
    assert "resourceId" in task.description


def test_load_task_detects_fsq_codex_yaml(tmp_path: Path) -> None:
    case_path = tmp_path / "case.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")

    task = load_task(case_path)

    assert task.name == "Fundamental Test bing.com website"
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


def test_fsq_case_loader_rejects_single_document_yaml(tmp_path: Path) -> None:
    case_path = tmp_path / "bad.codex.yaml"
    case_path.write_text("schemaVersion: fsq.ai-test/v1\nname: Bad\nplatform: android\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid FSQ case file"):
        FsqCaseLoader().load_case(case_path)
