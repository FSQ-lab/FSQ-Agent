import asyncio
import inspect
import json
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fsq_agent.models import LifecycleControllerSettings, RunEvent, RunEventSink, Task, ToolExecutionError


class MCPToolCaller:
    def __init__(
        self,
        servers: list[Any],
        run_id: str,
        task_id: str,
        event_sink: RunEventSink | None = None,
    ) -> None:
        self.servers = {str(getattr(server, "name", "")): server for server in servers}
        self.run_id = run_id
        self.task_id = task_id
        self.event_sink = event_sink

    async def call(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        server = self._server(server_name)

        started = time.perf_counter()
        call_id = f"lifecycle:{server_name}:{tool_name}:{int(started * 1000)}"
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_started",
                title="Lifecycle tool call started",
                message=f"Calling lifecycle tool {server_name}.{tool_name}.",
                tool_name=tool_name,
                tool_call_id=call_id,
                tool_arguments=arguments,
                payload={"tool_origin": "mcp", "server_name": server_name, "lifecycle": True},
            )
        )
        try:
            result = await server.call_tool(tool_name, arguments)
        except Exception as exc:
            await self._emit(
                RunEvent(
                    run_id=self.run_id,
                    task_id=self.task_id,
                    type="tool_call_failed",
                    title="Lifecycle tool call failed",
                    message=str(exc),
                    tool_name=tool_name,
                    tool_call_id=call_id,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    payload={"tool_origin": "mcp", "server_name": server_name, "lifecycle": True},
                )
            )
            raise

        output_preview = self._preview_result(result)
        is_error = bool(getattr(result, "isError", False))
        event_type = "tool_call_failed" if is_error else "tool_call_completed"
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type=event_type,
                title="Lifecycle tool call completed" if not is_error else "Lifecycle tool call failed",
                message=output_preview if is_error else "Lifecycle tool returned output.",
                tool_name=tool_name,
                tool_call_id=call_id,
                tool_output_preview=output_preview,
                duration_ms=int((time.perf_counter() - started) * 1000),
                payload={"tool_origin": "mcp", "server_name": server_name, "lifecycle": True},
            )
        )
        if is_error:
            raise ToolExecutionError(
                f"Lifecycle MCP tool {tool_name} returned an error: {output_preview}",
                context={"server": server_name, "tool": tool_name, "output": output_preview},
            )
        return result

    def server_env(self, server_name: str) -> dict[str, str]:
        params = getattr(self._server(server_name), "params", None)
        env = getattr(params, "env", None)
        if isinstance(env, Mapping):
            return {str(key): str(value) for key, value in env.items()}
        return {}

    def _server(self, server_name: str) -> Any:
        server = self.servers.get(server_name)
        if server is None:
            raise ToolExecutionError("Lifecycle MCP server is not available.", context={"server": server_name})
        return server

    async def _emit(self, event: RunEvent) -> None:
        if not self.event_sink:
            return
        result = self.event_sink(event)
        if inspect.isawaitable(result):
            await result

    def _preview_result(self, result: Any, limit: int = 1000) -> str:
        text = self._result_text(result)
        return text if len(text) <= limit else f"{text[:limit]}..."

    def _result_text(self, result: Any) -> str:
        content = getattr(result, "content", None)
        if isinstance(content, list):
            parts = []
            for item in content:
                text = getattr(item, "text", None)
                if text is not None:
                    parts.append(str(text))
                    continue
                model_dump = getattr(item, "model_dump", None)
                if callable(model_dump):
                    parts.append(json.dumps(model_dump(mode="json"), ensure_ascii=False))
                else:
                    parts.append(str(item))
            return "\n".join(parts)
        model_dump = getattr(result, "model_dump", None)
        if callable(model_dump):
            return json.dumps(model_dump(mode="json"), ensure_ascii=False)
        return str(result)


class LifecycleController(ABC):
    @abstractmethod
    async def batch_setup(self, caller: MCPToolCaller) -> None:
        raise NotImplementedError

    @abstractmethod
    async def case_setup(self, caller: MCPToolCaller, task: Task) -> None:
        raise NotImplementedError

    @abstractmethod
    async def case_teardown(self, caller: MCPToolCaller, task: Task) -> None:
        raise NotImplementedError

    @abstractmethod
    async def batch_teardown(self, caller: MCPToolCaller) -> None:
        raise NotImplementedError

    def runtime_policy(self) -> list[str]:
        return []


class NoopLifecycleController(LifecycleController):
    async def batch_setup(self, caller: MCPToolCaller) -> None:
        return None

    async def case_setup(self, caller: MCPToolCaller, task: Task) -> None:
        return None

    async def case_teardown(self, caller: MCPToolCaller, task: Task) -> None:
        return None

    async def batch_teardown(self, caller: MCPToolCaller) -> None:
        return None


class AppiumAndroidLifecycleController(LifecycleController):
    def __init__(
        self,
        server_name: str = "appium-mcp",
        session_create_attempts: int = 3,
        session_create_retry_delay_seconds: float = 2.0,
    ) -> None:
        self.server_name = server_name
        self.session_create_attempts = max(1, session_create_attempts)
        self.session_create_retry_delay_seconds = max(0.0, session_create_retry_delay_seconds)
        self.session_created = False
        self.session_id: str | None = None
        self.app_id: str | None = None

    async def batch_setup(self, caller: MCPToolCaller) -> None:
        await self._create_session(caller)
        self.session_created = True
        self.app_id = self._android_app_id(caller)
        await caller.call(self.server_name, "appium_session_management", {"action": "list"})

    async def case_setup(self, caller: MCPToolCaller, task: Task) -> None:
        app_id = self._require_app_id(caller)
        await self._ignore_tool_error(caller, "appium_app_lifecycle", self._app_lifecycle_args("terminate", app_id))
        await caller.call(self.server_name, "appium_app_lifecycle", self._app_lifecycle_args("activate", app_id))
        await caller.call(self.server_name, "appium_app_lifecycle", self._app_lifecycle_args("query_state", app_id))
        return None

    async def case_teardown(self, caller: MCPToolCaller, task: Task) -> None:
        app_id = self._require_app_id(caller)
        await self._ignore_tool_error(caller, "appium_mobile_keyboard", {"action": "hide", "keys": [], "sessionId": self.session_id or ""})
        await self._ignore_tool_error(caller, "appium_alert", {"action": "dismiss", "buttonLabel": "", "sessionId": self.session_id or ""})
        await self._ignore_tool_error(caller, "appium_app_lifecycle", self._app_lifecycle_args("terminate", app_id))
        return None

    async def batch_teardown(self, caller: MCPToolCaller) -> None:
        if not self.session_created:
            return None
        try:
            await caller.call(self.server_name, "appium_session_management", {"action": "delete"})
        finally:
            self.session_created = False
            self.session_id = None
        try:
            await caller.call(self.server_name, "appium_session_management", {"action": "list"})
        except Exception:
            return None
        return None

    async def _ignore_tool_error(self, caller: MCPToolCaller, tool_name: str, arguments: dict[str, Any]) -> None:
        try:
            await caller.call(self.server_name, tool_name, arguments)
        except Exception:
            return None

    async def _create_session(self, caller: MCPToolCaller) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.session_create_attempts + 1):
            try:
                result = await caller.call(self.server_name, "appium_session_management", {"action": "create", "platform": "android"})
                self.session_id = self._session_id_from_result(result)
                return None
            except Exception as exc:
                last_error = exc
                if attempt >= self.session_create_attempts:
                    break
                if self.session_create_retry_delay_seconds:
                    await asyncio.sleep(self.session_create_retry_delay_seconds)
        if last_error:
            raise last_error
        raise ToolExecutionError(
            "Appium Android lifecycle could not create a session.",
            context={"server": self.server_name, "platform": "android"},
        )

    def _app_lifecycle_args(self, action: str, app_id: str) -> dict[str, Any]:
        return {
            "action": action,
            "id": app_id,
            "name": "",
            "path": "",
            "keepData": False,
            "applicationType": "User",
            "seconds": 5,
            "url": "",
            "waitForLaunch": True,
            "sessionId": self.session_id or "",
        }

    def _session_id_from_result(self, result: Any) -> str | None:
        text = self._result_text(result)
        match = re.search(r"session created successfully with ID:\s*([A-Za-z0-9-]+)", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _result_text(self, result: Any) -> str:
        content = getattr(result, "content", None)
        if isinstance(content, list):
            return "\n".join(str(getattr(item, "text", item)) for item in content)
        return str(result)

    def runtime_policy(self) -> list[str]:
        if not self.session_id:
            return []
        return [
            f"The runtime has already created exactly one Appium Android session for this MCP client. Because the strict Appium MCP tool schema requires sessionId, use sessionId {self.session_id!r} on every appium-mcp tool call that accepts sessionId.",
            "Do not pass an empty string as sessionId. Only pass the runtime-provided non-empty sessionId.",
            "Do not call appium_session_management from the agent; session creation and deletion are runtime lifecycle responsibilities.",
        ]

    def _require_app_id(self, caller: MCPToolCaller) -> str:
        if not self.app_id:
            self.app_id = self._android_app_id(caller)
        if not self.app_id:
            raise ToolExecutionError(
                "Appium Android lifecycle requires appium:appPackage in CAPABILITIES_CONFIG.",
                context={"server": self.server_name, "platform": "android"},
            )
        return self.app_id

    def _android_app_id(self, caller: MCPToolCaller) -> str | None:
        path = caller.server_env(self.server_name).get("CAPABILITIES_CONFIG")
        if not path:
            return None
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        android = payload.get("android")
        if not isinstance(android, dict):
            return None
        app_id = android.get("appium:appPackage") or android.get("appPackage")
        return str(app_id) if app_id else None


class LifecycleControllerFactory:
    _ALIASES = {
        "": NoopLifecycleController,
        "none": NoopLifecycleController,
        "noop": NoopLifecycleController,
        "NoopLifecycleController": NoopLifecycleController,
        "appium_android": AppiumAndroidLifecycleController,
        "AppiumAndroidLifecycleController": AppiumAndroidLifecycleController,
    }

    @classmethod
    def create(cls, settings: LifecycleControllerSettings) -> LifecycleController:
        controller_cls = cls._ALIASES.get(settings.controller)
        if controller_cls is None:
            raise ToolExecutionError(
                "Unknown lifecycle controller.",
                context={"controller": settings.controller, "available": sorted(cls._ALIASES)},
            )
        return controller_cls(**settings.options)