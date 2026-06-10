from pathlib import Path
import json

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


def test_run_strict_core_batch_command_is_registered() -> None:
    assert "run-strict-core-batch" in main.commands


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


def test_run_strict_core_command_can_enable_ai_assertion_evaluator(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case_path = cases_dir / "strict_cli_ai.codex.yaml"
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
openai_agents:
  provider: azure_openai
  api_key_env: TEST_OPENAI_API_KEY
  model: gpt-test
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_OPENAI_API_KEY", "dummy")
    calls = {}

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str) -> None:
            calls["driver"] = {"app_id": app_id, "serial": serial}

    class FakeEvaluator:
        def __init__(self, settings) -> None:
            calls["evaluator_settings"] = settings

    class CapturingHarness:
        def __init__(self, *, driver, artifact_store, ai_assertion_evaluator=None) -> None:
            calls["harness"] = {
                "driver": driver,
                "artifact_store": artifact_store,
                "ai_assertion_evaluator": ai_assertion_evaluator,
            }

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
    monkeypatch.setattr("fsq_agent.cli._main.OpenAIAssertionEvaluator", FakeEvaluator)
    monkeypatch.setattr("fsq_agent.cli._main.AndroidHarness", CapturingHarness)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(
        main,
        [
            "run-strict-core",
            "--config",
            str(config_path),
            "--task",
            "strict_cli_ai.codex.yaml",
            "--android-serial",
            "device-1",
            "--run-id",
            "strict-run-ai",
            "--enable-ai-assertions",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls["evaluator_settings"].openai_agents.model == "gpt-test"
    assert isinstance(calls["harness"]["ai_assertion_evaluator"], FakeEvaluator)


def test_run_strict_core_batch_continues_and_writes_summary(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    first_case = cases_dir / "first.codex.yaml"
    second_case = cases_dir / "second.codex.yaml"
    first_case.write_text(FSQ_CASE.replace("Strict CLI Case", "First Case"), encoding="utf-8")
    second_case.write_text(FSQ_CASE.replace("Strict CLI Case", "Second Case"), encoding="utf-8")
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
    calls = []

    class FakeDriver:
        def __init__(self, *, app_id: str, serial: str) -> None:
            self.app_id = app_id
            self.serial = serial

    class CapturingHarness:
        def __init__(self, *, driver, artifact_store, ai_assertion_evaluator=None) -> None:
            self.driver = driver
            self.artifact_store = artifact_store
            self.ai_assertion_evaluator = ai_assertion_evaluator

    def fake_run_strict_fsq_core_case(**kwargs):
        calls.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True, exist_ok=True)
        report_path = kwargs["output_dir"] / "core-report.md"
        json_report_path = kwargs["output_dir"] / "core-report.json"
        manifest_path = kwargs["output_dir"] / "evidence-manifest.json"
        case_status = "failed" if kwargs["case_path"].name == "second.codex.yaml" else "passed"
        report_path.write_text("report", encoding="utf-8")
        json_report_path.write_text(
            json.dumps({"summary": {"status": case_status, "failed_steps": 1 if case_status == "failed" else 0}}),
            encoding="utf-8",
        )
        manifest_path.write_text("{}", encoding="utf-8")
        return ReportArtifact(
            run_id=kwargs["run_id"],
            path=report_path,
            evidence_manifest_path=manifest_path,
        )

    monkeypatch.setattr("fsq_agent.cli._main.UiAutomator2AndroidDriver", FakeDriver)
    monkeypatch.setattr("fsq_agent.cli._main.AndroidHarness", CapturingHarness)
    monkeypatch.setattr("fsq_agent.cli._main.run_strict_fsq_core_case", fake_run_strict_fsq_core_case)

    result = CliRunner().invoke(
        main,
        [
            "run-strict-core-batch",
            "--config",
            str(config_path),
            "--tasks",
            str(cases_dir),
            "--android-serial",
            "device-1",
            "--run-prefix",
            "batch-test",
        ],
    )

    assert result.exit_code == 1, result.output
    assert [call["case_path"].name for call in calls] == ["first.codex.yaml", "second.codex.yaml"]
    summary_path = workspace / "output" / "runs" / "batch-test" / "strict-core-batch-summary.json"
    markdown_path = workspace / "output" / "runs" / "batch-test" / "strict-core-batch-summary.md"
    assert summary_path.exists()
    assert markdown_path.exists()
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["failed"] == 1
    assert [case["status"] for case in summary["cases"]] == ["passed", "failed"]
    assert "failed_steps=1" in summary["cases"][1]["error"]
    assert "first.codex.yaml" in markdown_path.read_text(encoding="utf-8")


def test_task_from_goal_creates_goal_only_task() -> None:
    task = _task_from_goal("  Access Downloads through the overflow menu.  ")

    assert task.id == "access-downloads-through-the-overflow-menu"
    assert task.name == "Access Downloads through the overflow menu."
    assert task.key_actions == []
    assert task.verification_goal == "Goal completed: Access Downloads through the overflow menu."
    assert [criterion.kind for criterion in task.verification_criteria] == ["goal"]
