from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import mimetypes
from pathlib import Path
import re
import shutil
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import webbrowser

from fsq_agent.config import Settings
from fsq_agent.fsq import FsqCaseLoader
from fsq_agent.playground._android import build_android_setup_schema, capture_android_screenshot, resolve_auto_session
from fsq_agent.playground._execution import start_dynamic_goal_execution
from fsq_agent.playground._state import BusyError, PlaygroundState
from fsq_agent.report import resolve_report_path


@dataclass(frozen=True)
class PlaygroundServerOptions:
    host: str = "127.0.0.1"
    port: int = 8765
    open_browser: bool = True
    static_path: Path | None = None
    record: bool = True
    record_on_failure: bool = True


class PlaygroundServer:
    def __init__(self, settings: Settings, options: PlaygroundServerOptions | None = None) -> None:
        self.settings = settings
        self.options = options or PlaygroundServerOptions()
        self.state = PlaygroundState()
        self._httpd: _PlaygroundHTTPServer | None = None
        self._thread: Thread | None = None
        self._static_root = (self.options.static_path or Path(__file__).parent / "static").resolve()

    @property
    def url(self) -> str:
        return f"http://{self.options.host}:{self.port}"

    @property
    def port(self) -> int:
        if self._httpd is not None:
            return int(self._httpd.server_address[1])
        return self.options.port

    def start(self) -> None:
        if self._httpd is not None:
            return
        if not self._static_root.exists():
            raise FileNotFoundError(f"Playground static assets not found: {self._static_root}")
        self._httpd = _PlaygroundHTTPServer((self.options.host, self.options.port), _RequestHandler, self)
        self._thread = Thread(target=self._httpd.serve_forever, name="fsq-playground-server", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def serve_forever(self) -> None:
        self.start()
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            return
        finally:
            self.stop()

    def handle_get(self, path: str, query: dict[str, list[str]]) -> tuple[int, object]:
        if path == "/status":
            return 200, self.state.status()
        if path == "/session":
            return 200, self.state.session.to_json()
        if path == "/session/setup":
            return 200, build_android_setup_schema(self.settings)
        if path == "/runtime-info":
            return 200, self._runtime_info()
        if path == "/screenshot":
            if not self.state.session.connected:
                return 200, {"available": False, "error": "No active session."}
            try:
                payload = capture_android_screenshot(self.settings, self.state.session.device_id)
                if payload.get("available") is True and self.state.current_request_id:
                    self._record_replay_frame(self.state.current_request_id, payload)
                return 200, payload
            except Exception as exc:  # noqa: BLE001 - API returns structured errors.
                return 500, {"available": False, "error": str(exc) or exc.__class__.__name__}
        if path.startswith("/replay/"):
            request_id = unquote(path.removeprefix("/replay/")).strip()
            return self._replay_response(request_id)
        if path.startswith("/replay-video/"):
            replay_id = unquote(path.removeprefix("/replay-video/")).strip()
            return self._replay_video_response(replay_id)
        if path.startswith("/task-progress/"):
            request_id = unquote(path.removeprefix("/task-progress/")).strip()
            task = self.state.get_task(request_id, after_sequence=_after_sequence(query))
            if task is None:
                return 404, {"error": "Task progress not found."}
            return 200, task
        if path.startswith("/preview/"):
            request_id = unquote(path.removeprefix("/preview/")).strip()
            return self._preview_response(request_id)
        if path.startswith("/reports/"):
            return self._report_response(path, query)
        return 404, {"error": "Not found."}

    def _preview_response(self, request_id: str) -> tuple[int, object]:
        task = self.state.get_task(request_id)
        preview = task.get("preview") if task else None
        if not isinstance(preview, dict):
            return 404, {"error": "Preview not found."}
        run_id = preview.get("runId")
        path = preview.get("path")
        if not isinstance(run_id, str) or not isinstance(path, str):
            return 404, {"error": "Preview not found."}
        run_dir = Path(self.settings.output.runs_dir) / run_id
        preview_path = (run_dir / path).resolve()
        if not _is_relative_to(preview_path, run_dir) or not preview_path.is_file():
            return 404, {"error": "Preview not found."}
        return 200, {
            "requestId": request_id,
            "runId": run_id,
            "timestamp": preview.get("timestamp"),
            "token": preview.get("token"),
            "screenshot": base64.b64encode(preview_path.read_bytes()).decode("ascii"),
        }

    def handle_replay_video_file(self, path: str) -> tuple[int, bytes, str]:
        replay_id = unquote(path.removeprefix("/replay-video-file/")).strip()
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        video_path = self._replay_video_path(run_id)
        if not video_path.exists():
            payload = {"available": False, "error": "Replay video not found.", "runId": run_id}
            return 404, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        return 200, video_path.read_bytes(), "video/webm"

    def handle_post(self, path: str, body: dict[str, object]) -> tuple[int, object]:
        if path == "/session":
            device_id = body.get("deviceId")
            if not isinstance(device_id, str) or not device_id.strip():
                return 400, {"error": "deviceId is required."}
            try:
                return 200, {"session": self.state.create_session(device_id), "runtimeInfo": self._runtime_info()}
            except BusyError as exc:
                return 409, {"error": str(exc)}
        if path == "/session/auto":
            try:
                session, info = resolve_auto_session(self.settings)
                if session is None:
                    status = 500 if info.get("reason") == "adb_error" else 409
                    return status, {"error": info.get("message") or "Unable to auto-create Android session.", **info}
                created = self.state.create_session(session.device_id or "")
                created["displayName"] = session.display_name
                created["metadata"] = session.metadata
                self.state.session.display_name = session.display_name
                self.state.session.metadata = session.metadata
                return 200, {"session": created, "runtimeInfo": self._runtime_info(), "autoCreate": info}
            except BusyError as exc:
                return 409, {"error": str(exc)}
        if path == "/execute":
            goal = body.get("goal")
            case_yaml_path = body.get("caseYamlPath")
            strict_case_yaml_path = body.get("strictCaseYamlPath")
            has_goal = isinstance(goal, str) and bool(goal.strip())
            has_case_yaml = isinstance(case_yaml_path, str) and bool(case_yaml_path.strip())
            has_strict_case_yaml = isinstance(strict_case_yaml_path, str) and bool(strict_case_yaml_path.strip())
            if sum([has_goal, has_case_yaml, has_strict_case_yaml]) != 1:
                return 400, {"error": "Exactly one of goal, caseYamlPath, or strictCaseYamlPath is required."}
            if not self.state.session.connected:
                return 409, {"error": "No active Android session. Create a session before execution."}
            if has_goal:
                task_label = goal.strip()
            elif has_case_yaml:
                task_label = f"Case YAML: {case_yaml_path.strip()}"
            else:
                task_label = f"Strict YAML: {strict_case_yaml_path.strip()}"
            try:
                request_id = self.state.start_task(task_label)
            except BusyError as exc:
                return 409, {"error": str(exc)}
            if has_strict_case_yaml:
                self._reset_replay_for_known_run(request_id, self._strict_case_run_id(strict_case_yaml_path.strip()))
            start_dynamic_goal_execution(
                settings=self.settings,
                state=self.state,
                request_id=request_id,
                goal=goal.strip() if has_goal else None,
                case_yaml_path=case_yaml_path.strip() if has_case_yaml else None,
                strict_case_yaml_path=strict_case_yaml_path.strip() if has_strict_case_yaml else None,
                device_id=self.state.session.device_id,
                record=self.options.record,
                record_on_failure=self.options.record_on_failure,
            )
            return 202, {"requestId": request_id}
        if path.startswith("/replay-video/"):
            replay_id = unquote(path.removeprefix("/replay-video/")).strip()
            return self._store_replay_video(replay_id, body)
        return 404, {"error": "Not found."}

    def handle_delete(self, path: str) -> tuple[int, object]:
        if path == "/session":
            try:
                return 200, {"session": self.state.destroy_session(), "runtimeInfo": self._runtime_info()}
            except BusyError as exc:
                return 409, {"error": str(exc)}
        return 404, {"error": "Not found."}

    def static_response(self, path: str) -> tuple[int, bytes, str]:
        relative = "index.html" if path in {"/", "/index.html"} else unquote(path.lstrip("/"))
        candidate = (self._static_root / relative).resolve()
        if not candidate.is_file() or not _is_relative_to(candidate, self._static_root):
            candidate = self._static_root / "index.html"
        if not candidate.is_file() or not _is_relative_to(candidate.resolve(), self._static_root):
            return 404, b"Not found", "text/plain; charset=utf-8"
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or candidate.suffix in {".js", ".css", ".html"}:
            content_type = f"{content_type}; charset=utf-8"
        return 200, candidate.read_bytes(), content_type

    def _runtime_info(self) -> dict[str, object]:
        return {
            "platformId": "android",
            "title": "FSQ-Agent Android Playground",
            "interface": {"type": "Android", "description": "FSQ-Agent Android harness"},
            "preview": {"kind": "screenshot", "screenshotPath": "/screenshot", "live": False},
            "session": self.state.session.to_json(),
            "metadata": {
                "appIdPresent": bool(self.settings.harness.android.app_id),
                "configuredSerial": self.settings.harness.android.serial,
                "selectedDeviceId": self.state.session.device_id,
                "busy": self.state.current_request_id is not None,
                "lastRun": self.state.last_run,
            },
        }

    def _report_response(self, path: str, query: dict[str, list[str]]) -> tuple[int, object]:
        run_id = unquote(path.removeprefix("/reports/")).strip()
        report_format = (query.get("format") or ["markdown"])[0]
        if report_format not in {"markdown", "json"}:
            return 400, {"error": "format must be markdown or json."}
        try:
            report_path = resolve_report_path(self.settings.output.runs_dir, run_id, report_format)  # type: ignore[arg-type]
            return 200, {"runId": run_id, "format": report_format, "path": str(report_path), "content": report_path.read_text(encoding="utf-8")}
        except Exception as exc:  # noqa: BLE001 - API returns structured errors.
            return 404, {"error": str(exc) or exc.__class__.__name__}

    def _record_replay_frame(self, request_id: str, screenshot_payload: dict[str, object]) -> None:
        screenshot = screenshot_payload.get("screenshot")
        timestamp = screenshot_payload.get("timestamp")
        if not isinstance(screenshot, str) or not isinstance(timestamp, int):
            return
        run_id = self.state.run_id_for_request(request_id)
        if not run_id:
            return
        replay_dir = self._replay_dir(run_id)
        self._reset_replay_dir_once(request_id, replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = replay_dir / "replay-manifest.json"
        manifest = self._read_replay_manifest(manifest_path, request_id, run_id)
        frames = manifest["frames"]
        if frames and frames[-1].get("timestamp") == timestamp:
            return
        frame_index = len(frames) + 1
        frame_name = f"frame-{frame_index:04d}-{timestamp}.png"
        frame_path = replay_dir / frame_name
        frame_path.write_bytes(base64.b64decode(screenshot))
        frames.append({"timestamp": timestamp, "path": frame_name})
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        self.state.set_replay(
            request_id,
            {"requestId": request_id, "runId": run_id, "frameCount": len(frames)},
        )

    def _replay_response(self, replay_id: str) -> tuple[int, object]:
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        manifest_path = self._replay_dir(run_id) / "replay-manifest.json"
        if not manifest_path.exists():
            return self._evidence_replay_response(replay_id, run_id)
        manifest = self._read_replay_manifest(manifest_path, replay_id, run_id)
        frames = []
        for frame in manifest["frames"]:
            frame_path = (manifest_path.parent / str(frame.get("path") or "")).resolve()
            if not _is_relative_to(frame_path, manifest_path.parent) or not frame_path.is_file():
                continue
            frames.append(
                {
                    "timestamp": frame.get("timestamp"),
                    "screenshot": base64.b64encode(frame_path.read_bytes()).decode("ascii"),
                }
            )
        return 200, {"requestId": replay_id, "runId": run_id, "frames": frames}

    def _evidence_replay_response(self, replay_id: str, run_id: str) -> tuple[int, object]:
        run_dir = Path(self.settings.output.runs_dir) / run_id
        manifest_path = run_dir / "evidence-manifest.json"
        frames = []
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return 404, {"error": str(exc) or "Unable to read evidence manifest."}
            timestamps_by_path = self._screenshot_event_timestamps(manifest)
            frames.extend(self._frames_from_artifact_refs(run_dir, manifest.get("artifacts", []), timestamps_by_path))
        if not frames:
            frames.extend(self._event_replay_frames(run_dir))
        frames.sort(key=lambda frame: frame.get("timestamp") or 0)
        if not frames:
            return 404, {"error": "Replay frames not found."}
        return 200, {"requestId": replay_id, "runId": run_id, "frames": frames}

    def _frames_from_artifact_refs(
        self,
        run_dir: Path,
        artifact_refs: object,
        timestamps_by_path: dict[str, int] | None = None,
    ) -> list[dict[str, object]]:
        if not isinstance(artifact_refs, list):
            return []
        timestamps = timestamps_by_path or {}
        frames: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for artifact in artifact_refs:
            if not isinstance(artifact, dict) or not self._is_screenshot_artifact_ref(artifact):
                continue
            relative_path = str(artifact.get("path") or "")
            if not relative_path or relative_path in seen_paths:
                continue
            seen_paths.add(relative_path)
            frame_path = (run_dir / relative_path).resolve()
            if not _is_relative_to(frame_path, run_dir) or not frame_path.is_file():
                continue
            frames.append(
                {
                    "timestamp": timestamps.get(relative_path) or self._artifact_timestamp(artifact),
                    "screenshot": base64.b64encode(frame_path.read_bytes()).decode("ascii"),
                }
            )
        return frames

    def _event_replay_frames(self, run_dir: Path) -> list[dict[str, object]]:
        events_path = run_dir / "events.jsonl"
        if not events_path.exists():
            return []
        refs: list[dict[str, object]] = []
        seen_paths: set[str] = set()
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") not in {"tool_call_completed", "tool_call_failed"}:
                continue
            timestamp = self._timestamp_ms(event.get("timestamp"))
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            artifact_refs = payload.get("artifact_refs")
            if isinstance(artifact_refs, list):
                for ref in artifact_refs:
                    self._append_event_artifact_ref(refs, seen_paths, ref, timestamp)
            artifact_path = payload.get("artifact_path")
            if isinstance(artifact_path, str) and artifact_path:
                self._append_event_artifact_ref(refs, seen_paths, {"kind": "screenshot", "path": artifact_path}, timestamp)
        return self._frames_from_artifact_refs(run_dir, refs)

    def _append_event_artifact_ref(
        self,
        refs: list[dict[str, object]],
        seen_paths: set[str],
        ref: object,
        timestamp: int | None,
    ) -> None:
        if not isinstance(ref, dict) or not self._is_screenshot_artifact_ref(ref):
            return
        path = ref.get("path")
        if not isinstance(path, str) or not path or path in seen_paths:
            return
        seen_paths.add(path)
        refs.append({**ref, "timestamp": ref.get("timestamp") or timestamp})

    def _artifact_timestamp(self, artifact: dict[str, object]) -> int | None:
        timestamp = artifact.get("timestamp")
        if isinstance(timestamp, int):
            return timestamp
        return self._timestamp_ms(artifact.get("created_at"))

    def _is_screenshot_artifact_ref(self, ref: dict[str, object]) -> bool:
        if ref.get("kind") == "screenshot":
            return True
        path = ref.get("path")
        if not isinstance(path, str):
            return False
        normalized = path.replace("\\", "/").lower()
        return "/screenshots/" in normalized and normalized.endswith((".png", ".jpg", ".jpeg", ".webp"))

    def _screenshot_event_timestamps(self, manifest: dict[str, object]) -> dict[str, int]:
        timestamps: dict[str, int] = {}
        events = manifest.get("events")
        if not isinstance(events, list):
            return timestamps
        for event in events:
            if not isinstance(event, dict) or event.get("event_type") != "artifact_captured":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict) or payload.get("kind") != "screenshot":
                continue
            path = payload.get("path")
            timestamp = self._timestamp_ms(event.get("timestamp"))
            if isinstance(path, str) and timestamp is not None:
                timestamps[path] = timestamp
        return timestamps

    def _timestamp_ms(self, value: object) -> int | None:
        if not isinstance(value, str):
            return None
        try:
            normalized = value.replace("Z", "+00:00")
            return int(time.mktime(time.strptime(normalized[:19], "%Y-%m-%dT%H:%M:%S")) * 1000)
        except ValueError:
            return None

    def _replay_video_response(self, replay_id: str) -> tuple[int, object]:
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        video_path = self._replay_video_path(run_id)
        if not video_path.exists():
            return 200, {"available": False, "error": "Replay video not found.", "runId": run_id}
        return 200, {
            "available": True,
            "requestId": replay_id,
            "runId": run_id,
            "format": "webm",
            "videoUrl": f"/replay-video-file/{run_id}",
        }

    def _read_replay_manifest(self, manifest_path: Path, request_id: str, run_id: str) -> dict[str, object]:
        if manifest_path.exists():
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                frames = payload.get("frames") if isinstance(payload, dict) else None
                if isinstance(frames, list):
                    video = payload.get("video") if isinstance(payload.get("video"), dict) else None
                    return {"requestId": request_id, "runId": run_id, "frames": frames, "video": video}
            except (OSError, json.JSONDecodeError):
                pass
        return {"requestId": request_id, "runId": run_id, "frames": []}

    def _store_replay_video(self, replay_id: str, body: dict[str, object]) -> tuple[int, object]:
        run_id = self.state.run_id_for_request(replay_id) or replay_id
        video_base64 = body.get("videoBase64")
        mime_type = body.get("mimeType")
        if not isinstance(video_base64, str) or not video_base64.strip():
            return 400, {"error": "videoBase64 is required."}
        if not isinstance(mime_type, str) or not mime_type.lower().startswith("video/webm"):
            return 400, {"error": "Only video/webm replay uploads are supported."}
        replay_dir = self._replay_dir(run_id)
        self._reset_replay_dir_once(replay_id, replay_dir)
        replay_dir.mkdir(parents=True, exist_ok=True)
        video_path = replay_dir / "replay.webm"
        try:
            video_path.write_bytes(base64.b64decode(video_base64))
        except Exception as exc:  # noqa: BLE001 - API returns structured errors.
            return 400, {"error": str(exc) or "Invalid replay video."}
        manifest_path = replay_dir / "replay-manifest.json"
        manifest = self._read_replay_manifest(manifest_path, replay_id, run_id)
        manifest["video"] = {"path": "replay.webm", "mimeType": "video/webm"}
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return 200, {
            "available": True,
            "requestId": replay_id,
            "runId": run_id,
            "videoUrl": f"/replay-video-file/{run_id}",
            "mimeType": "video/webm",
        }

    def _replay_dir(self, run_id: str) -> Path:
        slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", run_id).strip("-") or "run"
        return Path(self.settings.output.runs_dir) / slug / "playground-replay"

    def _replay_video_path(self, run_id: str) -> Path:
        return self._replay_dir(run_id) / "replay.webm"

    def _reset_replay_dir_once(self, request_id: str, replay_dir: Path) -> None:
        if self.state.mark_replay_reset(request_id) and replay_dir.exists():
            shutil.rmtree(replay_dir)

    def _reset_replay_for_known_run(self, request_id: str, run_id: str | None) -> None:
        if not run_id:
            return
        self.state.bind_run_id(request_id, run_id)
        self._reset_replay_dir_once(request_id, self._replay_dir(run_id))

    def _strict_case_run_id(self, path_text: str) -> str | None:
        try:
            return FsqCaseLoader().load_case(self._resolve_case_yaml_path(path_text)).id
        except Exception:
            return None

    def _resolve_case_yaml_path(self, path_text: str) -> Path:
        requested = Path(path_text.strip())
        candidates = [requested] if requested.is_absolute() else [self.settings.cases.dir / requested, Path.cwd() / requested]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        raise FileNotFoundError(path_text)


class _PlaygroundHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], playground: PlaygroundServer) -> None:
        super().__init__(server_address, handler_class)
        self.playground = playground


class _RequestHandler(BaseHTTPRequestHandler):
    server: _PlaygroundHTTPServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
        parsed = urlparse(self.path)
        if parsed.path.startswith("/replay-video-file/"):
            status, payload, content_type = self.server.playground.handle_replay_video_file(parsed.path)
            self._send_bytes(status, payload, content_type)
            return
        if _is_api_path(parsed.path):
            status, payload = self.server.playground.handle_get(parsed.path, parse_qs(parsed.query))
            self._send_json(status, payload)
            return
        status, payload, content_type = self.server.playground.static_response(parsed.path)
        self._send_bytes(status, payload, content_type)

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API.
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if isinstance(body, str):
            self._send_json(400, {"error": body})
            return
        status, payload = self.server.playground.handle_post(parsed.path, body)
        self._send_json(status, payload)

    def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API.
        parsed = urlparse(self.path)
        status, payload = self.server.playground.handle_delete(parsed.path)
        self._send_json(status, payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
        return None

    def _read_json_body(self) -> dict[str, object] | str:
        content_length = int(self.headers.get("Content-Length") or "0")
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return "Request body must be valid JSON."
        if not isinstance(body, dict):
            return "Request body must be a JSON object."
        return body

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_playground(settings: Settings, options: PlaygroundServerOptions) -> None:
    server = PlaygroundServer(settings, options)
    server.start()
    try:
        print(f"Playground: {server.url}")
        if options.open_browser:
            webbrowser.open(server.url)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return
    finally:
        server.stop()


def _is_api_path(path: str) -> bool:
    return path in {"/status", "/session", "/session/setup", "/session/auto", "/runtime-info", "/screenshot"} or path.startswith(
        ("/task-progress/", "/preview/", "/reports/", "/replay/", "/replay-video/")
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _after_sequence(query: dict[str, list[str]]) -> int | None:
    values = query.get("after_sequence") or query.get("afterSequence") or []
    if not values:
        return None
    try:
        return max(0, int(values[0]))
    except (TypeError, ValueError):
        return None