from __future__ import annotations

from dataclasses import dataclass
import json
import mimetypes
from pathlib import Path
from threading import Thread
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import webbrowser

from fsq_agent.config import Settings
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
                return 200, capture_android_screenshot(self.settings, self.state.session.device_id)
            except Exception as exc:  # noqa: BLE001 - API returns structured errors.
                return 500, {"available": False, "error": str(exc) or exc.__class__.__name__}
        if path.startswith("/task-progress/"):
            request_id = unquote(path.removeprefix("/task-progress/")).strip()
            task = self.state.get_task(request_id)
            if task is None:
                return 404, {"error": "Task progress not found."}
            return 200, task
        if path.startswith("/reports/"):
            return self._report_response(path, query)
        return 404, {"error": "Not found."}

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
            if not isinstance(goal, str) or not goal.strip():
                return 400, {"error": "goal is required."}
            if not self.state.session.connected:
                return 409, {"error": "No active Android session. Create a session before execution."}
            try:
                request_id = self.state.start_task(goal.strip())
            except BusyError as exc:
                return 409, {"error": str(exc)}
            start_dynamic_goal_execution(
                settings=self.settings,
                state=self.state,
                request_id=request_id,
                goal=goal.strip(),
                device_id=self.state.session.device_id,
            )
            return 202, {"requestId": request_id}
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
            "title": "fsq-agent Android Playground",
            "interface": {"type": "Android", "description": "fsq-agent Android harness"},
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


class _PlaygroundHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], playground: PlaygroundServer) -> None:
        super().__init__(server_address, handler_class)
        self.playground = playground


class _RequestHandler(BaseHTTPRequestHandler):
    server: _PlaygroundHTTPServer

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler API.
        parsed = urlparse(self.path)
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
        ("/task-progress/", "/reports/")
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False