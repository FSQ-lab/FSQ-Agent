import base64
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
    assert progress["runId"] == "run-1"
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


def test_playground_server_persists_replay_frames(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-1").decode("ascii"), "timestamp": 1000},
    )
    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-2").decode("ascii"), "timestamp": 1800},
    )

    status, payload = server.handle_get(f"/replay/{request_id}", {})
    progress = server.state.get_task(request_id)

    assert status == 200
    assert [frame["timestamp"] for frame in payload["frames"]] == [1000, 1800]
    assert base64.b64decode(payload["frames"][0]["screenshot"]) == b"frame-1"
    assert (settings.output.runs_dir / "run-1" / "playground-replay" / "replay-manifest.json").exists()
    assert progress is not None
    assert progress["replay"]["runId"] == "run-1"
    assert progress["replay"]["frameCount"] == 2
    assert "manifestPath" not in progress["replay"]


def test_playground_server_replay_uses_evidence_screenshots(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    run_dir = settings.output.runs_dir / "run-1"
    screenshot_dir = run_dir / "artifacts" / "screenshots"
    screenshot_dir.mkdir(parents=True)
    (screenshot_dir / "step-1.png").write_bytes(b"evidence-frame")
    (run_dir / "evidence-manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "events": [
                    {
                        "event_type": "artifact_captured",
                        "timestamp": "2026-06-17T10:49:07Z",
                        "payload": {"kind": "screenshot", "path": "artifacts/screenshots/step-1.png"},
                    }
                ],
                "artifacts": [
                    {"kind": "screenshot", "path": "artifacts/screenshots/step-1.png"},
                ],
            }
        ),
        encoding="utf-8",
    )
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))

    status, payload = server.handle_get("/replay/run-1", {})

    assert status == 200
    assert payload["runId"] == "run-1"
    assert isinstance(payload["frames"][0]["timestamp"], int)
    assert base64.b64decode(payload["frames"][0]["screenshot"]) == b"evidence-frame"


def test_playground_server_preview_endpoint_returns_latest_screenshot(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    screenshot_path = settings.output.runs_dir / "run-1" / "artifacts" / "screenshots" / "step-1.png"
    screenshot_path.parent.mkdir(parents=True)
    screenshot_path.write_bytes(b"preview")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Strict")
    server.state.set_preview(
        request_id,
        {
            "runId": "run-1",
            "path": "artifacts/screenshots/step-1.png",
            "timestamp": "2026-06-17T10:49:07+00:00",
            "token": "run-1:step-1",
        },
    )

    status, payload = server.handle_get(f"/preview/{request_id}", {})

    assert status == 200
    assert payload["token"] == "run-1:step-1"
    assert base64.b64decode(payload["screenshot"]) == b"preview"


def test_playground_server_resets_replay_dir_once_per_request(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    replay_dir = settings.output.runs_dir / "run-1" / "playground-replay"
    replay_dir.mkdir(parents=True)
    (replay_dir / "old-frame.png").write_bytes(b"old")
    (replay_dir / "replay.webm").write_bytes(b"old-video")
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-1").decode("ascii"), "timestamp": 1000},
    )
    server._record_replay_frame(
        request_id,
        {"available": True, "screenshot": base64.b64encode(b"frame-2").decode("ascii"), "timestamp": 1800},
    )

    assert not (replay_dir / "old-frame.png").exists()
    assert not (replay_dir / "replay.webm").exists()
    assert sorted(path.name for path in replay_dir.glob("frame-*.png")) == [
        "frame-0001-1000.png",
        "frame-0002-1800.png",
    ]


def test_playground_server_stores_uploaded_replay_video(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    status, payload = server.handle_post(
        f"/replay-video/{request_id}",
        {"mimeType": "video/webm", "videoBase64": base64.b64encode(b"webm").decode("ascii")},
    )
    video_status, video_bytes, content_type = server.handle_replay_video_file(f"/replay-video-file/{request_id}")

    assert status == 200
    assert payload["videoUrl"] == "/replay-video-file/run-1"
    assert (settings.output.runs_dir / "run-1" / "playground-replay" / "replay.webm").read_bytes() == b"webm"
    assert video_status == 200
    assert video_bytes == b"webm"
    assert content_type == "video/webm"


def test_playground_server_accepts_webm_upload_with_codecs(tmp_path: Path) -> None:
    settings = Settings()
    settings.output.runs_dir = tmp_path / "runs"
    server = PlaygroundServer(settings, PlaygroundServerOptions(static_path=tmp_path))
    request_id = server.state.start_task("Replay me")
    server.state.add_event(request_id, RunEvent(run_id="run-1", task_id="task", type="run_started", title="Run started"))

    status, payload = server.handle_post(
        f"/replay-video/{request_id}",
        {"mimeType": "video/webm;codecs=vp8", "videoBase64": base64.b64encode(b"webm").decode("ascii")},
    )

    assert status == 200
    assert payload["videoUrl"] == "/replay-video-file/run-1"


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
    strict_both_status, strict_both_payload = server.handle_post("/execute", {"caseYamlPath": "case.codex.yaml", "strictCaseYamlPath": "case.codex.yaml"})

    assert missing_status == 400
    assert "Exactly one" in missing_payload["error"]
    assert both_status == 400
    assert "Exactly one" in both_payload["error"]
    assert strict_both_status == 400
    assert "Exactly one" in strict_both_payload["error"]


def test_playground_execute_starts_strict_yaml(monkeypatch) -> None:
    captured = {}

    def fake_start_dynamic_goal_execution(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", fake_start_dynamic_goal_execution)
    server = PlaygroundServer(Settings())
    server.state.create_session("device-1")

    status, payload = server.handle_post("/execute", {"strictCaseYamlPath": "case.codex.yaml"})

    assert status == 202
    assert payload["requestId"]
    assert captured["goal"] is None
    assert captured["case_yaml_path"] is None
    assert captured["strict_case_yaml_path"] == "case.codex.yaml"


def test_playground_execute_clears_strict_replay_dir_at_start(tmp_path: Path, monkeypatch) -> None:
    settings = Settings()
    settings.cases.dir = tmp_path / "cases"
    settings.output.runs_dir = tmp_path / "runs"
    settings.cases.dir.mkdir()
    case_path = settings.cases.dir / "strict_case.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Strict Case
platform: android
---
- launchApp
""",
        encoding="utf-8",
    )
    replay_dir = settings.output.runs_dir / "strict_case" / "playground-replay"
    replay_dir.mkdir(parents=True)
    (replay_dir / "old-frame.png").write_bytes(b"old")
    monkeypatch.setattr("fsq_agent.playground._server.start_dynamic_goal_execution", lambda **_kwargs: None)
    server = PlaygroundServer(settings)
    server.state.create_session("device-1")

    status, _payload = server.handle_post("/execute", {"strictCaseYamlPath": "strict_case.codex.yaml"})

    assert status == 202
    assert not replay_dir.exists()


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
    clear_page_body = script[script.index("function clearPage()"):script.index("async function refreshStatus()")]

    assert html.index('class="section progress-section"') < html.index("<h2>Session</h2>")
    assert "FSQ-Agent Playground" in html
    assert "status-pill status-connecting" in html
    assert "preview-tab" in html
    assert "report-tab" in html
    assert "report-content" in html
    assert "preview-pane" in html
    assert '<button id="replay-screenshots" type="button">Replay</button>' in html
    assert 'id="replay-video"' in html
    assert '<button id="refresh" type="button">Clear</button>' in html
    assert "progress-run-id" in html
    assert "progressSequence" in script
    assert "setServerStatus" in script
    assert "status-pill status-${status}" in script
    assert "progressDetailOpenState" in script
    assert "screenshotTimer" not in script
    assert "screenshotInFlight" not in script
    assert "replayFrames" in script
    assert "replayTimer" in script
    assert "replayIndex" in script
    assert "replayRequestId" in script
    assert "previewToken" in script
    assert "replayVideoInFlight" in script
    assert "liveVideoRecorder" not in script
    assert "liveVideoChunks" not in script
    assert "function clearPage()" in script
    assert "els.refresh.addEventListener('click', clearPage)" in script
    assert "window.clearInterval(state.progressTimer)" in script
    assert "stopLiveScreenshotPolling" not in script
    assert "stopReplay();" in clear_page_body
    assert "clearRunId();" in clear_page_body
    assert "els.progress.innerHTML = ''" in script
    assert "els.reportContent.textContent = ''" in script
    assert "clearPreview();" in clear_page_body
    assert "clearPreview('Loading live preview...')" in script
    assert "function clearPreview" in script
    assert "els.screenshot.removeAttribute('src')" in script
    assert "refreshStatus();" in clear_page_body
    assert "els.sessionMessage.textContent = ''" not in clear_page_body
    assert "els.deviceSelect.innerHTML = ''" not in clear_page_body
    assert "captureProgressDetailState" in script
    assert "data-detail-key" in script
    assert "event.sequence" in script
    assert "backendSequence" in script
    assert "tool_arguments" in script
    assert "tool_output_preview" in script
    assert "event.payload" in script
    assert "eventDetails" in script
    assert 'name="run-mode"' in html
    assert "strict-yaml" in html
    assert "caseYaml" in script
    assert "runYaml" in script
    assert "runSelected" in script
    assert "currentRunMode() === 'strict-yaml'" in script
    assert "currentRunMode" in script
    assert "updateRunMode" in script
    assert "caseYamlPath" in script
    assert "strictCaseYamlPath" in script
    assert "loadReport" in script
    assert "?format=markdown" in script
    assert "renderMarkdown" in script
    assert "escapeHtml" in script
    assert "showRightTab" in script
    assert "renderProgressText" in script
    assert "toolName" in script
    assert "progressRunId" in script
    assert "function setRunId(runId)" in script
    assert "function clearRunId()" in script
    assert "setRunId(event.run_id || event.runId)" in script
    assert "setRunId(progress.result.runId)" in script
    assert "event.type === 'run_started'" in script
    assert "Run ID: ${runId}" in script
    assert "refreshPreviewFromReplay" in script
    assert "refreshPreview" in script
    assert "api(`/preview/${encodeURIComponent(requestId)}`)" in script
    assert "startLiveScreenshotPolling" not in script
    assert "refreshScreenshot({ preservePrevious: true })" not in script
    assert "preloadImage" in script
    assert "startReplay" in script
    assert "stopReplay" in script
    assert "showReplayFrame" in script
    assert "loadReplayFrames" in script
    assert "loadReplayVideo" in script
    assert "playReplayVideo" in script
    assert "generateReplayVideo" in script
    assert "recordLiveReplayFrame" not in script
    assert "finalizeLiveReplayVideo" not in script
    assert "Replay video saved" in script
    assert "Replay video was not generated:" in script
    assert "MediaRecorder produced an empty video" in script
    assert "no replay frames found" in script
    assert "discardLiveReplayVideo" not in script
    assert "ensureReplayVideoGenerated" in script
    assert "replayVideoMimeType" in script
    assert "MediaRecorder.isTypeSupported" in script
    assert "uploadReplayVideo" in script
    assert "blobToBase64" in script
    assert "els.replayVideo.addEventListener('ended'" in script
    assert "api(`/replay-video/${encodeURIComponent(requestId)}`)" in script
    assert "method: 'POST'" in script
    assert "recorder.start(1000)" in script
    assert "video.videoUrl" in script
    assert "scheduleNextReplayFrame" in script
    assert "replayFrameDelay" in script
    assert "els.replayScreenshots.addEventListener('click', startReplay)" in script
    assert "api(`/replay/${encodeURIComponent(requestId)}`)" in script
    assert "next.timestamp - current.timestamp" in script
    assert "window.setTimeout" in script
    assert "window.clearTimeout" in script
    assert "No replay frames yet." in script
    assert "No replay run yet." in script
    assert "Unable to load replay" in script
    assert "eventStatus" in script
    assert "statusFromValue" in script
    assert "progress-status-${status}" in script
    assert "/session/auto" in script
    assert "ensureSession" in script
    assert "padStart(3, '0')" in script
    assert "progress-number" in styles
    assert "#replay-video" in styles
    assert "status-pill" in styles
    assert "status-ready" in styles
    assert "status-running" in styles
    assert "status-error" in styles
    assert "progress-run-id" in styles
    assert "flex: 0 0 auto" in styles
    assert "progress-title" in styles
    assert "progress-message" in styles
    assert "progress-tool" in styles
    assert "progress-detail" in styles
    assert "progress-status-dot" in styles
    assert "progress-status-success" in styles
    assert "progress-status-failed" in styles
    assert "screenshot-refresh" not in styles
    assert "#22c55e" in styles
    assert "#ef4444" in styles
    assert "grid-template-rows: auto minmax(0, 1fr) auto auto" in styles
    assert "grid-template-rows: auto minmax(420px, 62vh) auto auto" in styles
    assert "run-mode-row" in styles
    assert "report-pane" in styles
    assert "report-content" in styles
    assert "tab-button.active" in styles
    assert "[hidden]" in styles