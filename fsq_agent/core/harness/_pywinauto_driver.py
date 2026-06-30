from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import time
from typing import Any, TypeVar

from pydantic import BaseModel

from fsq_agent.core.harness._driver_tools import _windows_driver_tool
from fsq_agent.models import (
    ConfigurationError,
    WindowsAssertVisibleParams,
    WindowsClickOnParams,
    WindowsDoubleClickOnParams,
    WindowsKillAppParams,
    WindowsLaunchAppParams,
    WindowsPressKeyParams,
    WindowsRightClickOnParams,
    WindowsTypeTextParams,
    WindowsUiSnapshotParams,
)


DEFAULT_WINDOWS_WAIT_TIMEOUT_SECONDS = 10.0
WINDOW_READY_TIMEOUT_SECONDS = 30.0
_T = TypeVar("_T")


class PywinautoWindowsDriver:
    backend = "pywinauto"

    def __init__(
        self,
        *,
        app_path: str | Path | None = None,
        backend_kind: str = "uia",
        window_title_re: str | None = None,
        launch_args: list[str] | None = None,
        window: object | None = None,
    ) -> None:
        self.app_path = str(Path(app_path)) if app_path else None
        self.backend_kind = backend_kind
        self.window_title_re = window_title_re.strip() if isinstance(window_title_re, str) and window_title_re.strip() else None
        self.launch_args = list(launch_args) if launch_args else []
        self._app: object | None = None
        self._window: object | None = window
        self._executor: ThreadPoolExecutor | None = None if window is not None else ThreadPoolExecutor(max_workers=1, thread_name_prefix="fsq-pywinauto")

    def context(self) -> dict[str, object]:
        return self._run_sync(self._context_payload)

    def _context_payload(self) -> dict[str, object]:
        return {
            "session_id": f"pywinauto:{self.backend_kind}",
            "current_url": None,
            "screen_size": self._window_size(),
            "metadata": {
                "backend": self.backend,
                "backend_kind": self.backend_kind,
                "app_path_configured": self.app_path is not None,
                "window_title_re_configured": self.window_title_re is not None,
            },
        }

    @_windows_driver_tool(
        "launchApp",
        description="Launch the configured Windows desktop application.",
        capture_evidence=True,
        metadata={"evidence_capture_before": False, "evidence_capture_on_failure": False},
    )
    def launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        return self._run_sync(lambda: self._launch_app(params))

    def _launch_app(self, params: WindowsLaunchAppParams) -> dict[str, object]:
        app_path = params.app_path or self.app_path
        if not app_path:
            return self._failed("configuration_error", "Windows app path is not configured.")
        application_cls = self._application_cls()
        launch_args = [*self.launch_args, *(params.extra_args or [])]
        cmd = subprocess.list2cmdline([app_path, *launch_args])
        application_cls(backend=self.backend_kind).start(cmd)
        self._window = self._resolve_main_window()
        return self._passed({"app_path": app_path, "launch_args": launch_args, "window_title_re": self.window_title_re})

    def _resolve_main_window(self) -> object:
        if not self.window_title_re:
            connected = self._application_cls()(backend=self.backend_kind).connect(active_only=True)
            self._app = connected
            return connected.top_window()
        # Find the application window by title across the desktop. Multi-process apps such
        # as Microsoft Edge own their visible window in a different process than the one
        # launched, so connect by title instead of scoping to the launched process id.
        application_cls = self._application_cls()
        deadline = time.monotonic() + WINDOW_READY_TIMEOUT_SECONDS
        while True:
            try:
                connected = application_cls(backend=self.backend_kind).connect(title_re=self.window_title_re)
                window = connected.window(title_re=self.window_title_re, control_type="Window")
                window.wait("exists visible enabled", timeout=2)
                self._app = connected
                return window
            except Exception:  # noqa: BLE001 - retry until the window appears or timeout.
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1.0)

    @_windows_driver_tool("killApp", description="Stop the launched Windows desktop application.")
    def kill_app(self, params: WindowsKillAppParams) -> dict[str, object]:
        return self._run_sync(self._kill_app)

    def _kill_app(self) -> dict[str, object]:
        if self._app is not None:
            kill = getattr(self._app, "kill", None)
            if callable(kill):
                kill()
        self._app = None
        self._window = None
        return self._passed()

    @_windows_driver_tool("clickOn", description="Click a Windows control resolved from the UI snapshot.", capture_evidence=True)
    def click_on(self, params: WindowsClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._click_on(params))

    def _click_on(self, params: WindowsClickOnParams) -> dict[str, object]:
        control = self._control(params)
        if control is None:
            return self._target_missing(params)
        button = params.button or "left"
        if params.double:
            control.double_click_input(button=button)
        else:
            control.click_input(button=button)
        return self._passed()

    @_windows_driver_tool("doubleClickOn", description="Double-click a Windows control.", capture_evidence=True)
    def double_click_on(self, params: WindowsDoubleClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._double_click_on(params))

    def _double_click_on(self, params: WindowsDoubleClickOnParams) -> dict[str, object]:
        control = self._control(params)
        if control is None:
            return self._target_missing(params)
        control.double_click_input(button=params.button or "left")
        return self._passed()

    @_windows_driver_tool("rightClickOn", description="Right-click a Windows control.", capture_evidence=True)
    def right_click_on(self, params: WindowsRightClickOnParams) -> dict[str, object]:
        return self._run_sync(lambda: self._right_click_on(params))

    def _right_click_on(self, params: WindowsRightClickOnParams) -> dict[str, object]:
        control = self._control(params)
        if control is None:
            return self._target_missing(params)
        control.click_input(button="right")
        return self._passed()

    @_windows_driver_tool("typeText", description="Type text into a Windows control.", capture_evidence=True)
    def type_text(self, params: WindowsTypeTextParams) -> dict[str, object]:
        return self._run_sync(lambda: self._type_text(params))

    def _type_text(self, params: WindowsTypeTextParams) -> dict[str, object]:
        control = self._control(params)
        if control is None:
            return self._target_missing(params)
        control.click_input()
        if params.clear:
            control.type_keys("^a{BACKSPACE}", set_foreground=True)
        control.type_keys(params.text, with_spaces=True, set_foreground=True)
        return self._passed()

    @_windows_driver_tool("pressKey", description="Send a keyboard key sequence to the active Windows window.", capture_evidence=True)
    def press_key(self, params: WindowsPressKeyParams) -> dict[str, object]:
        return self._run_sync(lambda: self._press_key(params))

    def _press_key(self, params: WindowsPressKeyParams) -> dict[str, object]:
        window = self._require_window()
        window.type_keys(params.key, with_spaces=True, set_foreground=True)
        return self._passed({"key": params.key})

    @_windows_driver_tool("assertVisible", description="Assert that a Windows control is visible.")
    def assert_visible(self, params: WindowsAssertVisibleParams) -> dict[str, object]:
        return self._run_sync(lambda: self._assert_visible(params))

    def _assert_visible(self, params: WindowsAssertVisibleParams) -> dict[str, object]:
        control = self._control(params)
        if control is not None and control.is_visible():
            return self._passed()
        return self._target_missing(params)

    @_windows_driver_tool("uiSnapshot", description="Return the current Windows window control tree snapshot.")
    def ui_snapshot(self, params: WindowsUiSnapshotParams) -> dict[str, object]:
        return self._run_sync(self._ui_snapshot)

    def _ui_snapshot(self) -> dict[str, object]:
        window = self._require_window()
        texts = getattr(window, "texts", None)
        title = texts()[0] if callable(texts) else None
        return {"title": title if isinstance(title, str) else None, "snapshot_type": "control_tree"}

    def screenshot(self, params: object | None = None) -> bytes:
        return self._run_sync(self._screenshot)

    def _screenshot(self) -> bytes:
        from io import BytesIO

        window = self._require_window()
        image = window.capture_as_image()
        if image is None:
            raise ConfigurationError(
                "Windows screenshot capture returned no image. Pillow is required for pywinauto screenshots.",
                context={"install": "pip install fsq-agent[windows]"},
            )
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def close(self) -> None:
        try:
            self._run_sync(self._kill_app)
        finally:
            self._shutdown_executor()

    def _run_sync(self, func: Callable[[], _T]) -> _T:
        if self._executor is None:
            return func()
        return self._executor.submit(func).result()

    def _shutdown_executor(self) -> None:
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True)

    def _application_cls(self) -> Any:
        try:
            from pywinauto import Application
        except ImportError as exc:
            raise ConfigurationError(
                "pywinauto is required for PywinautoWindowsDriver.",
                context={"install": "pip install fsq-agent[windows]"},
            ) from exc
        return Application

    def _require_window(self) -> Any:
        if self._window is None:
            raise ConfigurationError("Windows window is not available; launch the app first.")
        return self._window

    def _control(self, params: BaseModel) -> Any:
        data = params.model_dump(mode="python", exclude_none=True)
        locator = data.get("locator")
        if isinstance(locator, dict):
            return self._control_from_kwargs(locator)
        target = data.get("target")
        if isinstance(target, str) and target.strip():
            return self._child_window(title_re=f".*{target}.*", found_index=0)
        return None

    def _control_from_kwargs(self, locator: dict[str, Any]) -> Any:
        kwargs: dict[str, Any] = {}
        if isinstance(locator.get("title"), str):
            kwargs["title"] = locator["title"]
        if isinstance(locator.get("control_type"), str):
            kwargs["control_type"] = locator["control_type"]
        if isinstance(locator.get("automation_id"), str):
            kwargs["auto_id"] = locator["automation_id"]
        if isinstance(locator.get("class_name"), str):
            kwargs["class_name"] = locator["class_name"]
        index = locator.get("index")
        kwargs["found_index"] = (index - 1) if isinstance(index, int) and index >= 1 else 0
        if not kwargs:
            return None
        control = self._child_window(**kwargs)
        return control if control is not None and control.exists() else None

    def _child_window(self, **kwargs: Any) -> Any:
        window = self._require_window()
        return window.child_window(**kwargs)

    def _window_size(self) -> tuple[int, int] | None:
        if self._window is None:
            return None
        rectangle = getattr(self._window, "rectangle", None)
        if not callable(rectangle):
            return None
        rect = rectangle()
        width = getattr(rect, "width", None)
        height = getattr(rect, "height", None)
        if callable(width) and callable(height):
            return int(width()), int(height())
        return None

    def _target_missing(self, params: BaseModel) -> dict[str, object]:
        return self._failed(
            "target_resolution_error",
            "Target was not found.",
            metadata={"params": params.model_dump(mode="json", exclude_none=True)},
        )

    def _passed(self, output: object | None = None) -> dict[str, object]:
        return {"status": "passed", "output": output}

    def _failed(
        self,
        failure_category: str,
        error_message: str,
        *,
        output: object | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, object]:
        return {
            "status": "failed",
            "failure_category": failure_category,
            "error_message": error_message,
            "output": output,
            "metadata": metadata or {},
        }
