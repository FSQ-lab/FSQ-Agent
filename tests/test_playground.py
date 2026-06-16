import json
from pathlib import Path
from urllib.request import urlopen

from fsq_agent.config import Settings
from fsq_agent.models import ReportArtifact, RunEvent, TaskResult, VerificationResult
from fsq_agent.playground._android import AndroidTarget, parse_adb_devices, resolve_auto_session
from fsq_agent.playground._execution import task_from_case_yaml, task_from_goal
from fsq_agent.playground._server import PlaygroundServer, PlaygroundServerOptions
from fsq_agent.playground._state import BusyError, PlaygroundState


def test_parse_adb_devices_discovers_default_device() -> None:
    output = """List of devices attached
emulator-5554 device product:sdk_gphone64_x86_64 model:sdk_gphone64_x86_64 device:emu64xa transport_id:1
offline-1 offline
"""

    targets = parse_adb_devices(output)

    assert len(targets) == 1
    assert targets[0].id == "emulator-5554"
    assert targets[0].is_default is True
    assert "sdk gphone64 x86 64" in targets[0].description


def test_task_from_goal_matches_dynamic_goal_contract() -> None:
    task = task_from_goal("  Open rewards panel  ")

    assert task.id == "open-rewards-panel"
    assert task.name == "Open rewards panel"
    assert task.planning_reference_kind == "goal"
    assert task.planning_reference_text == "Open rewards panel"
    assert task.verification_goal is None


def test_task_from_case_yaml_preserves_raw_reference(tmp_path: Path) -> None:
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    case_path = cases_dir / "sample.codex.yaml"
    content = "schemaVersion: fsq.ai-test/v1\nname: Sample\n---\n- launchApp\n"
    case_path.write_text(content, encoding="utf-8")
    settings = Settings()
    settings.cases.dir = cases_dir

    task = task_from_case_yaml("sample.codex.yaml", settings)

    assert task.name == "Case reference: sample.codex.yaml"
    assert task.planning_reference_kind == "raw_case"
    assert task.planning_reference_text is not None
    assert str(case_path.resolve()) in task.planning_reference_text
    assert content in task.planning_reference_text


def test_auto_session_uses_configured_serial_when_online(monkeypatch) -> None:
    settings = Settings()
    settings.harness.android.serial = "device-2"
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: (
            [
                AndroidTarget(id="device-1", label="device-1", is_default=True),
                AndroidTarget(id="device-2", label="device-2"),
            ],
            None,
        ),
    )

    session, info = resolve_auto_session(settings)

    assert session is not None
    assert session.device_id == "device-2"
    assert info["reason"] == "configured_serial"


def test_auto_session_reports_configured_serial_offline(monkeypatch) -> None:
    settings = Settings()
    settings.harness.android.serial = "missing-device"
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: ([AndroidTarget(id="device-1", label="device-1", is_default=True)], None),
    )

    session, info = resolve_auto_session(settings)

    assert session is None
    assert info["reason"] == "configured_serial_offline"
    assert info["configuredSerial"] == "missing-device"


def test_auto_session_uses_single_online_device(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: ([AndroidTarget(id="device-1", label="device-1", is_default=True)], None),
    )

    session, info = resolve_auto_session(Settings())

    assert session is not None
    assert session.device_id == "device-1"
    assert info["reason"] == "single_device"


def test_auto_session_requires_manual_selection_for_multiple_devices(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: (
            [
                AndroidTarget(id="device-1", label="device-1", is_default=True),
                AndroidTarget(id="device-2", label="device-2"),
            ],
            None,
        ),
    )

    session, info = resolve_auto_session(Settings())

    assert session is None
    assert info["reason"] == "multiple_devices"


def test_auto_session_reports_no_devices(monkeypatch) -> None:
    monkeypatch.setattr("fsq_agent.playground._android.discover_adb_targets", lambda: ([], None))

    session, info = resolve_auto_session(Settings())

    assert session is None
    assert info["reason"] == "no_devices"


def test_playground_state_locks_concurrent_tasks(tmp_path: Path) -> None:
    state = PlaygroundState()
    state.create_session("device-1")
    request_id = state.start_task("Do it")

    try:
        state.start_task("Do something else")
    except BusyError as exc:
        assert "already running" in str(exc)
    else:
        raise AssertionError("Expected BusyError")

    result = TaskResult(
        task_id="task",
        status="success",
        steps=[],
        verification=VerificationResult(status="success", summary="ok"),
        report=ReportArtifact(run_id="run-1", path=tmp_path / "report.md"),
    )
    state.add_event(
        request_id,
        RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"),
    )
    state.finish_task(request_id, result)

    progress = state.get_task(request_id)
    assert progress is not None
    assert progress["status"] == "success"
    assert progress["result"]["runId"] == "run-1"
    assert state.current_request_id is None


def test_playground_server_static_path_rejects_traversal(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("hello", encoding="utf-8")
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(static_path=static_dir))

    status, body, content_type = server.static_response("/../secret.txt")

    assert status == 200
    assert body == b"hello"
    assert content_type.startswith("text/html")


def test_playground_server_report_endpoint_returns_content(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    report_dir = settings.output.runs_dir / "run-1"
    report_dir.mkdir(parents=True)
    (report_dir / "report.md").write_text("# report", encoding="utf-8")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/reports/run-1", {})

    assert status == 200
    assert payload["runId"] == "run-1"
    assert payload["content"] == "# report"


def test_playground_execute_requires_session() -> None:
    server = PlaygroundServer(Settings())

    status, payload = server.handle_post("/execute", {"goal": "Do it"})

    assert status == 409
    assert "No active" in payload["error"]


def test_playground_execute_requires_exactly_one_source() -> None:
    server = PlaygroundServer(Settings())
    server.state.create_session("device-1")

    missing_status, missing_payload = server.handle_post("/execute", {})
    both_status, both_payload = server.handle_post("/execute", {"goal": "Do it", "caseYamlPath": "case.codex.yaml"})

    assert missing_status == 400
    assert "Exactly one" in missing_payload["error"]
    assert both_status == 400
    assert "Exactly one" in both_payload["error"]


def test_playground_auto_session_route_creates_single_device_session(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: ([AndroidTarget(id="device-1", label="device-1", is_default=True)], None),
    )
    server = PlaygroundServer(Settings())

    status, payload = server.handle_post("/session/auto", {})

    assert status == 200
    assert payload["session"]["deviceId"] == "device-1"
    assert payload["autoCreate"]["reason"] == "single_device"


def test_playground_auto_session_route_requires_manual_selection(monkeypatch) -> None:
    monkeypatch.setattr(
        "fsq_agent.playground._android.discover_adb_targets",
        lambda: (
            [
                AndroidTarget(id="device-1", label="device-1", is_default=True),
                AndroidTarget(id="device-2", label="device-2"),
            ],
            None,
        ),
    )
    server = PlaygroundServer(Settings())

    status, payload = server.handle_post("/session/auto", {})

    assert status == 409
    assert payload["reason"] == "multiple_devices"
    assert len(payload["targets"]) == 2


def test_playground_server_serves_status_over_http(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("hello", encoding="utf-8")
    server = PlaygroundServer(Settings(), PlaygroundServerOptions(port=0, static_path=static_dir, open_browser=False))
    server.start()
    try:
        with urlopen(f"{server.url}/status", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.stop()

    assert payload["status"] == "ok"
    assert payload["busy"] is False


def test_playground_static_progress_is_first_section_and_numbered() -> None:
    static_dir = Path(__file__).parents[1] / "fsq_agent" / "playground" / "static"
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    script = (static_dir / "playground.js").read_text(encoding="utf-8")
    styles = (static_dir / "playground.css").read_text(encoding="utf-8")

    assert html.index('class="section progress-section"') < html.index("<h2>Session</h2>")
    assert "preview-tab" in html
    assert "report-tab" in html
    assert "report-content" in html
    assert "preview-pane" in html
    assert "progressSequence" in script
    assert "event.sequence" in script
    assert "backendSequence" in script
    assert "tool_arguments" in script
    assert "tool_output_preview" in script
    assert "event.payload" in script
    assert "eventDetails" in script
    assert 'name="run-mode"' in html
    assert "caseYaml" in script
    assert "runYaml" in script
    assert "runSelected" in script
    assert "currentRunMode" in script
    assert "updateRunMode" in script
    assert "caseYamlPath" in script
    assert "loadReport" in script
    assert "?format=markdown" in script
    assert "showRightTab" in script
    assert "eventStatus" in script
    assert "statusFromValue" in script
    assert "progress-status-${status}" in script
    assert "/session/auto" in script
    assert "ensureSession" in script
    assert "padStart(3, '0')" in script
    assert "progress-number" in styles
    assert "progress-detail" in styles
    assert "progress-status-dot" in styles
    assert "progress-status-success" in styles
    assert "progress-status-failed" in styles
    assert "#22c55e" in styles
    assert "#ef4444" in styles
    assert "grid-template-rows: auto minmax(0, 1fr) auto auto" in styles
    assert "grid-template-rows: auto minmax(420px, 62vh) auto auto" in styles
    assert "run-mode-row" in styles
    assert "report-pane" in styles
    assert "report-content" in styles
    assert "tab-button.active" in styles
    assert "[hidden]" in styles