from pathlib import Path

from click.testing import CliRunner

from fsq_agent.cli._main import _task_from_goal, main
from fsq_agent.models import ReportArtifact


FSQ_CASE = """
schemaVersion: fsq.ai-test/v1
name: Strict CLI Case
platform: android
appId: com.microsoft.emmx
---
- launchApp
"""


def test_run_goal_command_is_registered() -> None:
    assert "run-goal" in main.commands


def test_run_strict_core_command_is_registered() -> None:
    assert "run-strict-core" in main.commands


def test_run_strict_core_command_builds_android_harness_and_reports_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case_path = cases_dir / "strict_cli.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
workspace:
  root_dir: {workspace.as_posix()}
cases:
  dir: {cases_dir.as_posix()}
output:
  root_dir: output
  runs_dir: runs
""",
        encoding="utf-8",
    )
    calls = {}

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str) -> None:
            calls["driver"] = {"app_id": app_id, "serial": serial}

    def fake_run_strict_fsq_core_case(**kwargs):
        calls["strict"] = kwargs
        report_path = kwargs["output_dir"] / "core-report.md"
        manifest_path = kwargs["output_dir"] / "evidence-manifest.json"
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        report_path.write_text("report", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(
            run_id=kwargs["run_id"],
            path=report_path,
            evidence_manifest_path=manifest_path,
        )

    monkeypatch.setattr("fsq_agent.cli._main.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(
        main,
        [
            "run-strict-core",
            "--config",
            str(config_path),
            "--task",
            "strict_cli.codex.yaml",
            "--android-serial",
            "device-1",
            "--run-id",
            "strict-run-1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls["driver"] == {"app_id": "com.microsoft.emmx", "serial": "device-1"}
    assert calls["strict"]["case_path"] == case_path.resolve()
    assert calls["strict"]["run_id"] == "strict-run-1"
    assert calls["strict"]["output_dir"] == workspace / "output" / "runs" / "strict-run-1"
    assert "core-report.md" in result.output
    assert "evidence-manifest.json" in result.output


def test_task_from_goal_creates_goal_only_task() -> None:
    task = _task_from_goal("  Access Downloads through the overflow menu.  ")

    assert task.id == "access-downloads-through-the-overflow-menu"
    assert task.name == "Access Downloads through the overflow menu."
    assert task.key_actions == []
    assert task.verification_goal == "Goal completed: Access Downloads through the overflow menu."
    assert [criterion.kind for criterion in task.verification_criteria] == ["goal"]
