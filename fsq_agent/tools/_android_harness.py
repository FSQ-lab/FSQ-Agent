import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any

from fsq_agent.models import HarnessPlatformSettings, PlatformActionDefinition, PlatformActionResult, RunEventSink, Task, ToolExecutionError
from fsq_agent.tools._harness import Harness
from fsq_agent.tools._platform import PlatformAdapter


class AndroidAppiumMCPBackend:
    _LOCATOR_STRATEGIES = (
        "accessibility id",
        "id",
        "-android uiautomator",
        "xpath",
        "name",
        "class name",
        "css selector",
    )

    def __init__(self, server: Any) -> None:
        self.server = server
        self.session_id: str | None = None

    @classmethod
    async def enter(cls, stack: Any, env: dict[str, str] | None = None, timeout_seconds: float = 100.0) -> "AndroidAppiumMCPBackend":
        try:
            from agents.mcp import MCPServerStdio
        except ImportError as exc:
            raise ToolExecutionError("openai-agents is required for the Android Appium backend.") from exc

        server = MCPServerStdio(
            params={"command": "npx", "args": ["-y", "appium-mcp@latest"], "env": env or {}},
            name="android-appium-backend",
            cache_tools_list=True,
            require_approval="never",
            client_session_timeout_seconds=timeout_seconds,
            tool_filter=None,
        )
        return cls(await stack.enter_async_context(server))

    async def call(self, action_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if action_name == "android_create_session":
            result = await self._call_mcp("appium_session_management", {"action": "create", "platform": "android"})
            if result.get("ok"):
                self.session_id = self._session_id_from_text(str(result.get("text") or ""))
                result["session_id"] = self.session_id
            return result
        if action_name == "android_delete_session":
            result = await self._call_mcp("appium_session_management", {"action": "delete"})
            if result.get("ok"):
                self.session_id = None
            return result
        if action_name == "android_activate_app":
            return await self._call_mcp("appium_app_lifecycle", self._app_lifecycle_args("activate", str(arguments.get("app_id") or "")))
        if action_name == "android_terminate_app":
            return await self._call_mcp("appium_app_lifecycle", self._app_lifecycle_args("terminate", str(arguments.get("app_id") or "")))
        if action_name == "android_query_app_state":
            return await self._call_mcp("appium_app_lifecycle", self._app_lifecycle_args("query_state", str(arguments.get("app_id") or "")))
        if action_name == "android_hide_keyboard":
            return await self._call_mcp("appium_mobile_keyboard", {"action": "hide", "keys": [], "sessionId": self.session_id or ""})
        if action_name == "android_dismiss_alert":
            return await self._call_mcp("appium_alert", {"action": "dismiss", "buttonLabel": "", "sessionId": self.session_id or ""})
        if action_name == "android_find_element":
            return await self._find_element_from_arguments(arguments)
        if action_name == "android_tap":
            if self._has_element_reference(arguments):
                resolved = await self._element_id_from_arguments(arguments)
                if not resolved.get("ok"):
                    return resolved
                return await self._call_mcp("appium_gesture", {"action": "tap", "elementUUID": resolved.get("element_id"), "sessionId": self.session_id or ""})
            if arguments.get("x") is not None and arguments.get("y") is not None:
                return await self._call_mcp(
                    "appium_gesture",
                    {"action": "tap", "x": int(arguments.get("x") or 0), "y": int(arguments.get("y") or 0), "sessionId": self.session_id or ""},
                )
            return self._action_error("android_tap requires element_id, target, strategy plus selector, or x plus y.")
        if action_name == "android_input_text":
            payload: dict[str, Any] = {"text": str(arguments.get("text") or ""), "sessionId": self.session_id or ""}
            if arguments.get("w3c_actions") is True or arguments.get("w3cActions") is True:
                payload["w3cActions"] = True
            else:
                resolved = await self._element_id_from_arguments(arguments)
                if not resolved.get("ok"):
                    return resolved
                payload["elementUUID"] = resolved.get("element_id")
            return await self._call_mcp("appium_set_value", payload)
        if action_name == "android_press_key":
            return await self._press_key(arguments)
        if action_name == "android_back":
            return await self._press_key({"key": "Back"})
        if action_name == "android_scroll_to_element":
            return await self._scroll_to_element(arguments)
        if action_name == "android_scroll":
            payload: dict[str, Any] = {"action": "scroll", "direction": str(arguments.get("direction") or "down"), "sessionId": self.session_id or ""}
            if arguments.get("duration") is not None:
                payload["duration"] = int(arguments.get("duration") or 0)
            resolved = await self._optional_element_id_from_arguments(arguments)
            if resolved.get("ok") and resolved.get("element_id"):
                payload["elementUUID"] = resolved.get("element_id")
            elif resolved.get("ok") is False:
                return resolved
            return await self._call_mcp("appium_gesture", payload)
        if action_name == "android_drag_and_drop":
            return await self._drag_and_drop(arguments)
        if action_name == "android_get_text":
            resolved = await self._element_id_from_arguments(arguments)
            if not resolved.get("ok"):
                return resolved
            return await self._call_mcp("appium_get_text", {"elementUUID": resolved.get("element_id"), "sessionId": self.session_id or ""})
        if action_name == "android_get_attribute":
            resolved = await self._element_id_from_arguments(arguments)
            if not resolved.get("ok"):
                return resolved
            return await self._call_mcp(
                "appium_get_element_attribute",
                {"elementUUID": resolved.get("element_id"), "attribute": str(arguments.get("attribute") or ""), "sessionId": self.session_id or ""},
            )
        if action_name == "android_page_source":
            result = await self._call_mcp("appium_get_page_source", {"sessionId": self.session_id or ""})
            return self._bounded_text_result(result, int(arguments.get("max_chars") or 8000), hard_limit=12000)
        if action_name == "android_window_size":
            return await self._call_mcp("appium_get_window_size", {"sessionId": self.session_id or ""})
        if action_name == "android_context":
            payload: dict[str, Any] = {"action": str(arguments.get("action") or "list"), "sessionId": self.session_id or ""}
            if arguments.get("context") is not None:
                payload["context"] = str(arguments.get("context") or "")
            return await self._call_mcp("appium_context", payload)
        if action_name == "android_device_info":
            payload = {"action": str(arguments.get("action") or "info"), "sessionId": self.session_id or ""}
            if arguments.get("format") is not None:
                payload["format"] = str(arguments.get("format") or "")
            return await self._call_mcp("appium_mobile_device_info", payload)
        if action_name == "android_wait":
            duration_ms = int(arguments.get("duration_ms") or 0)
            if duration_ms > 0:
                await asyncio.sleep(duration_ms / 1000)
            return {"ok": True, "duration_ms": duration_ms}
        if action_name == "android_screenshot":
            payload: dict[str, Any] = {"maxWidth": int(arguments.get("max_width") or arguments.get("maxWidth") or 600), "sessionId": self.session_id or ""}
            resolved = await self._optional_element_id_from_arguments(arguments)
            if resolved.get("ok") and resolved.get("element_id"):
                payload["elementUUID"] = resolved.get("element_id")
            elif resolved.get("ok") is False:
                return resolved
            return await self._call_mcp("appium_screenshot", payload)
        return {"ok": False, "error": f"Unsupported Android backend action: {action_name}", "failure_category": "unsupported_action"}

    async def _find_element_from_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        locators = self._locators_from_arguments(arguments)
        if not locators:
            return self._action_error("Provide target, element_id, or strategy plus selector.")
        last_result: dict[str, Any] | None = None
        for strategy, selector in locators:
            result = await self._find_element(strategy, selector)
            if result.get("ok"):
                return result
            last_result = result
        return last_result or {"ok": False, "error": "No Android locator was available.", "failure_category": "action_error"}

    async def _find_element(self, strategy: str, selector: str) -> dict[str, Any]:
        result = await self._call_mcp("appium_find_element", {"strategy": strategy, "selector": selector, "sessionId": self.session_id or ""})
        if result.get("ok"):
            result["strategy"] = strategy
            result["selector"] = selector
            result["element_id"] = self._element_id_from_text(str(result.get("text") or ""))
        return result

    async def _element_id_from_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        direct_element_id = self._direct_element_id(arguments)
        if direct_element_id:
            return {"ok": True, "element_id": direct_element_id}
        found = await self._find_element_from_arguments(arguments)
        if not found.get("ok"):
            return found
        element_id = found.get("element_id")
        if not element_id:
            return self._action_error("Element lookup succeeded but did not return an element id.")
        return {"ok": True, "element_id": element_id, "found": found}

    async def _optional_element_id_from_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if not self._has_element_reference(arguments):
            return {"ok": True}
        return await self._element_id_from_arguments(arguments)

    async def _scroll_to_element(self, arguments: dict[str, Any]) -> dict[str, Any]:
        locators = self._locators_from_arguments(arguments)
        if not locators:
            return self._action_error("android_scroll_to_element requires target or strategy plus selector.")
        strategy, selector = locators[0]
        payload: dict[str, Any] = {
            "action": "scroll_to_element",
            "strategy": strategy,
            "selector": selector,
            "direction": str(arguments.get("direction") or "down"),
            "maxScrollAttempts": int(arguments.get("max_scroll_attempts") or arguments.get("maxScrollAttempts") or 10),
            "sessionId": self.session_id or "",
        }
        if arguments.get("scroll_distance") is not None:
            payload["scrollDistance"] = float(arguments.get("scroll_distance") or 0)
        if arguments.get("scroll_distance_preset") is not None:
            payload["scrollDistancePreset"] = str(arguments.get("scroll_distance_preset"))
        return await self._call_mcp("appium_gesture", payload)

    async def _drag_and_drop(self, arguments: dict[str, Any]) -> dict[str, Any]:
        source = await self._drag_endpoint(arguments, "source")
        if not source.get("ok"):
            return source
        target = await self._drag_endpoint(arguments, "target")
        if not target.get("ok"):
            return target
        payload: dict[str, Any] = {"sessionId": self.session_id or ""}
        payload.update(source["payload"])
        payload.update(target["payload"])
        if arguments.get("duration") is not None:
            payload["duration"] = int(arguments.get("duration") or 0)
        long_press_duration = arguments.get("long_press_duration", arguments.get("longPressDuration"))
        if long_press_duration is not None:
            payload["longPressDuration"] = int(long_press_duration or 0)
        return await self._call_mcp("appium_drag_and_drop", payload)

    async def _drag_endpoint(self, arguments: dict[str, Any], prefix: str) -> dict[str, Any]:
        reference_args = self._prefixed_element_arguments(arguments, prefix)
        if self._has_element_reference(reference_args):
            resolved = await self._element_id_from_arguments(reference_args)
            if not resolved.get("ok"):
                return resolved
            return {"ok": True, "payload": {f"{prefix}ElementUUID": resolved.get("element_id")}}
        x_value = arguments.get(f"{prefix}_x", arguments.get(f"{prefix}X"))
        y_value = arguments.get(f"{prefix}_y", arguments.get(f"{prefix}Y"))
        if x_value is not None and y_value is not None:
            return {"ok": True, "payload": {f"{prefix}X": int(x_value or 0), f"{prefix}Y": int(y_value or 0)}}
        return self._action_error(f"android_drag_and_drop requires {prefix}_element_id, {prefix}_target, {prefix}_strategy plus {prefix}_selector, or {prefix}_x plus {prefix}_y.")

    async def _press_key(self, arguments: dict[str, Any]) -> dict[str, Any]:
        key_code_value = arguments.get("key_code", arguments.get("keyCode"))
        payload: dict[str, Any] = {"sessionId": self.session_id or ""}
        if key_code_value is not None:
            payload["keyCode"] = int(key_code_value)
        else:
            key = str(arguments.get("key") or "").strip()
            key_code = {"back": 4, "enter": 66}.get(key.lower())
            logical_key = {"home": "HOME", "app_switch": "APP_SWITCH", "appswitch": "APP_SWITCH"}.get(key.lower())
            if key_code is not None:
                payload["keyCode"] = key_code
            elif logical_key is not None:
                payload["key"] = logical_key
            else:
                payload["key"] = key.upper() if key else key
        if arguments.get("is_long_press") is not None:
            payload["isLongPress"] = bool(arguments.get("is_long_press"))
        return await self._call_mcp("appium_mobile_press_key", payload)

    def _locators_from_arguments(self, arguments: dict[str, Any]) -> list[tuple[str, str]]:
        strategy = str(arguments.get("strategy") or "").strip()
        selector = str(arguments.get("selector") or "").strip()
        if strategy and selector:
            return [(strategy, selector)]
        target = str(arguments.get("target") or "").strip()
        return self._locators_for_target(target) if target else []

    def _direct_element_id(self, arguments: dict[str, Any]) -> str | None:
        for key in ("element_id", "elementUUID"):
            value = str(arguments.get(key) or "").strip()
            if value:
                return self._element_id_from_text(value) or value
        target = str(arguments.get("target") or "").strip()
        return self._element_id_from_text(target) if target else None

    def _has_element_reference(self, arguments: dict[str, Any]) -> bool:
        return any(str(arguments.get(key) or "").strip() for key in ("element_id", "elementUUID", "target", "strategy", "selector"))

    def _prefixed_element_arguments(self, arguments: dict[str, Any], prefix: str) -> dict[str, Any]:
        return {
            "element_id": arguments.get(f"{prefix}_element_id") or arguments.get(f"{prefix}ElementUUID") or arguments.get(f"{prefix}_elementUUID"),
            "strategy": arguments.get(f"{prefix}_strategy"),
            "selector": arguments.get(f"{prefix}_selector"),
            "target": arguments.get(f"{prefix}_target"),
        }

    async def _call_mcp(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await self.server.call_tool(tool_name, arguments)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "failure_category": "backend_error", "mcp_tool": tool_name}
        text = self._result_text(result)
        if bool(getattr(result, "isError", False)):
            return {"ok": False, "error": text, "failure_category": "backend_error", "mcp_tool": tool_name, "text": text}
        payload: dict[str, Any] = {"ok": True, "mcp_tool": tool_name, "text": text}
        screenshot_path = self._screenshot_path_from_text(text)
        if screenshot_path:
            payload["evidence_refs"] = [screenshot_path]
        return payload

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

    def _locators_for_target(self, target: str) -> list[tuple[str, str]]:
        stripped = target.strip()
        lower = stripped.lower()
        for prefix, strategy in (
            ("accessibilityid=", "accessibility id"),
            ("accessibility id=", "accessibility id"),
            ("id=", "id"),
            ("resourceid=", "id"),
            ("xpath=", "xpath"),
        ):
            if lower.startswith(prefix):
                return [(strategy, stripped[len(prefix) :])]
        if stripped.startswith("//"):
            return [("xpath", stripped)]
        locators = [("accessibility id", stripped)]
        if ":id/" in stripped:
            locators.append(("id", stripped))
        escaped = stripped.replace("'", "\\'")
        locators.append(("xpath", f"//*[@text='{escaped}' or @content-desc='{escaped}']"))
        return locators

    def _bounded_text_result(self, result: dict[str, Any], max_chars: int, hard_limit: int | None = None) -> dict[str, Any]:
        if hard_limit is not None:
            max_chars = min(max_chars, hard_limit)
        text = str(result.get("text") or "")
        if max_chars > 0 and len(text) > max_chars:
            result = dict(result)
            result["text"] = text[:max_chars]
            result["truncated"] = True
            result["text_length"] = len(text)
        return result

    def _action_error(self, message: str) -> dict[str, Any]:
        return {"ok": False, "error": message, "failure_category": "action_error"}

    def _session_id_from_text(self, text: str) -> str | None:
        match = re.search(r"session created successfully with ID:\s*([A-Za-z0-9-]+)", text, re.IGNORECASE)
        return match.group(1) if match else None

    def _element_id_from_text(self, text: str) -> str | None:
        match = re.search(r"elementId[:\s]+['\"]?([^'\"\s]+)['\"]?", text)
        return match.group(1) if match else None

    def _screenshot_path_from_text(self, text: str) -> str | None:
        match = re.search(r"Screenshot saved successfully to:\s*(.+?)(?:\n|$)", text)
        return match.group(1).strip() if match else None

    def _result_text(self, result: Any) -> str:
        content = getattr(result, "content", None)
        if isinstance(content, list):
            return "\n".join(str(getattr(item, "text", item)) for item in content)
        model_dump = getattr(result, "model_dump", None)
        if callable(model_dump):
            return json.dumps(model_dump(mode="json"), ensure_ascii=False)
        return str(result)


class AndroidAppiumPlatformAdapter(PlatformAdapter):
    def __init__(self, settings: HarnessPlatformSettings, backend: Any = None) -> None:
        self.settings = settings
        self.backend = backend
        self.session_id: str | None = None
        self._actions = self._build_actions()

    def action_space(self) -> list[PlatformActionDefinition]:
        return list(self._actions)

    async def invoke_action(
        self,
        action_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> PlatformActionResult:
        definition = self.action_definition(action_name)
        if definition is None:
            return PlatformActionResult(
                action_name=action_name,
                status="failed",
                error=f"Unsupported Android action: {action_name}",
                failure_category="unsupported_action",
            )
        if self.backend is None:
            return PlatformActionResult(
                action_name=action_name,
                status="failed",
                error="Android Appium backend is not configured.",
                failure_category="backend_error",
            )
        started = time.perf_counter()
        try:
            result = await self.backend.call(action_name, params)
        except Exception as exc:
            return PlatformActionResult(
                action_name=action_name,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
                failure_category="backend_error",
                backend_debug={"backend_kind": "internal"},
            )
        normalized = self._normalize_backend_result(action_name, result, started)
        if action_name == "android_create_session" and isinstance(normalized.output, dict):
            session_id = normalized.output.get("session_id")
            if session_id:
                self.session_id = str(session_id)
        return normalized

    def app_id(self) -> str | None:
        path = self._capabilities_path()
        if path is None:
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        android = payload.get("android")
        if not isinstance(android, dict):
            return None
        app_id = android.get("appium:appPackage") or android.get("appPackage")
        return str(app_id) if app_id else None

    def _capabilities_path(self) -> Path | None:
        import os

        value = os.getenv(self.settings.capabilities_config_env)
        if value:
            return Path(value)
        return None

    def _normalize_backend_result(self, action_name: str, result: Any, started: float) -> PlatformActionResult:
        duration_ms = int((time.perf_counter() - started) * 1000)
        if isinstance(result, PlatformActionResult):
            if result.duration_ms == 0:
                result.duration_ms = duration_ms
            return result
        if isinstance(result, dict):
            status = "failed" if result.get("ok") is False or result.get("status") == "failed" else "success"
            return PlatformActionResult(
                action_name=action_name,
                status=status,
                duration_ms=duration_ms,
                output=result,
                error=str(result.get("error")) if result.get("error") else None,
                failure_category=result.get("failure_category"),
                evidence_refs=[str(value) for value in result.get("evidence_refs", [])],
                backend_debug={"backend_kind": "internal"},
            )
        return PlatformActionResult(
            action_name=action_name,
            status="success",
            duration_ms=duration_ms,
            output=result,
            backend_debug={"backend_kind": "internal"},
        )

    def _build_actions(self) -> list[PlatformActionDefinition]:
        return [
            self._action(
                "android_tap",
                "Tap an Android element. Prefer element_id from android_find_element or explicit strategy+selector; target is a convenience fallback. Do not provide coordinate fields.",
                input_schema=self._object_schema(self._element_reference_schema()),
            ),
            self._action(
                "android_input_text",
                "Enter text into an Android element. Use element_id or explicit strategy+selector when available; set w3c_actions only when typing into the focused control.",
                input_schema=self._object_schema(
                    {
                        **self._element_reference_schema(),
                        "text": {"type": "string", "description": "Text to input."},
                        "w3c_actions": {"type": "boolean", "description": "When true, type through W3C Actions into the currently focused element without resolving element_id."},
                    },
                    required=["text"],
                ),
            ),
            self._action(
                "android_press_key",
                "Press an Android navigation key or key code. Use key for Back, Enter, Home, or AppSwitch; use key_code for explicit Android keycodes.",
                input_schema=self._object_schema(
                    {
                        "key": {"type": "string", "description": "Semantic key name such as Back, Enter, Home, or AppSwitch."},
                        "key_code": {"type": "integer", "description": "Optional explicit Android keycode. Takes precedence over key."},
                        "is_long_press": {"type": "boolean", "description": "Whether to long-press the key."},
                    }
                ),
            ),
            self._action("android_back", "Navigate back on Android.", input_schema=self._object_schema({})),
            self._action(
                "android_scroll_to_element",
                "Scroll until an Android element appears. Mirrors Appium scroll_to_element and avoids repeated manual find/screenshot retries.",
                input_schema=self._object_schema(
                    {
                        **self._locator_schema(),
                        "target": {"type": "string", "description": "Convenience fallback target; explicit strategy+selector is preferred."},
                        "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Scroll direction. Defaults to down."},
                        "max_scroll_attempts": {"type": "integer", "minimum": 1, "maximum": 80, "description": "Maximum attempts before giving up. Defaults to 10."},
                        "scroll_distance": {"type": "number", "minimum": 0.05, "maximum": 1, "description": "Optional scroll length fraction."},
                        "scroll_distance_preset": {"type": "string", "enum": ["small", "medium", "large"], "description": "Optional scroll distance preset."},
                    }
                ),
            ),
            self._action(
                "android_scroll",
                "Scroll the current Android screen or a referenced scrollable element in one direction.",
                input_schema=self._object_schema(
                    {
                        **self._element_reference_schema(),
                        "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Scroll direction. Defaults to down."},
                        "duration": {"type": "integer", "minimum": 0, "maximum": 10000, "description": "Optional scroll duration in milliseconds."},
                    }
                ),
            ),
            self._action(
                "android_drag_and_drop",
                "Drag from a source element/location to a target element/location. Prefer source/target element_id or explicit locator fields; use coordinates only when no locator is available.",
                input_schema=self._object_schema(
                    {
                        **self._drag_endpoint_schema("source"),
                        **self._drag_endpoint_schema("target"),
                        "duration": {"type": "integer", "minimum": 100, "maximum": 5000, "description": "Drag movement duration in milliseconds. Defaults to backend value."},
                        "long_press_duration": {"type": "integer", "minimum": 400, "maximum": 2000, "description": "Long-press duration before dragging in milliseconds. Defaults to backend value."},
                    }
                ),
            ),
            self._action(
                "android_wait",
                "Wait without changing Android UI state.",
                input_schema=self._object_schema({"duration_ms": {"type": "integer", "minimum": 0, "description": "Wait duration in milliseconds."}}, required=["duration_ms"]),
                idempotent=True,
            ),
            self._action(
                "android_find_element",
                "Find one Android UI element and return element_id. Prefer explicit strategy+selector using Appium priority: accessibility id, id, -android uiautomator, xpath last.",
                input_schema=self._object_schema({**self._locator_schema(), "target": {"type": "string", "description": "Visible text, content description, resource id, xpath, or prefixed locator fallback."}}),
                idempotent=True,
            ),
            self._action(
                "android_get_text",
                "Get text from an Android element identified by element_id, strategy+selector, or target.",
                input_schema=self._object_schema(self._element_reference_schema()),
                idempotent=True,
            ),
            self._action(
                "android_get_attribute",
                "Get an Android element attribute such as enabled, selected, checked, focused, displayed, clickable, text, content-desc, resource-id, or class.",
                input_schema=self._object_schema({**self._element_reference_schema(), "attribute": {"type": "string", "description": "Attribute name to retrieve."}}, required=["attribute"]),
                idempotent=True,
            ),
            self._action(
                "android_page_source",
                "Get bounded XML page source for the current Android screen. Use for targeted diagnosis when precise locators are unclear; prefer smaller element queries first.",
                input_schema=self._object_schema({"max_chars": {"type": "integer", "minimum": 1000, "maximum": 12000, "description": "Maximum XML characters returned inline. Defaults to 8000 and is capped at 12000."}}),
                idempotent=True,
                evidence_policy="ui_tree",
            ),
            self._action(
                "android_window_size",
                "Get Android screen width and height in pixels for coordinate calculations.",
                input_schema=self._object_schema({}),
                idempotent=True,
            ),
            self._action(
                "android_context",
                "List Android/Appium contexts or switch context, for hybrid app flows that need NATIVE_APP/WEBVIEW context control.",
                input_schema=self._object_schema(
                    {
                        "action": {"type": "string", "enum": ["list", "switch"], "description": "Use list to fetch contexts or switch to change context."},
                        "context": {"type": "string", "description": "Required when action is switch, for example NATIVE_APP or WEBVIEW_<package>."},
                    },
                    required=["action"],
                ),
                idempotent=True,
            ),
            self._action(
                "android_device_info",
                "Get Android device information, battery status, or current device time.",
                input_schema=self._object_schema(
                    {
                        "action": {"type": "string", "enum": ["info", "battery", "time"], "description": "Data to retrieve."},
                        "format": {"type": "string", "description": "Optional moment.js time format when action is time."},
                    },
                    required=["action"],
                ),
                idempotent=True,
            ),
            self._action(
                "android_screenshot",
                "Capture an Android screenshot. Optionally capture a referenced element; max_width defaults to 600 to reduce model context.",
                input_schema=self._object_schema({**self._element_reference_schema(), "max_width": {"type": "integer", "minimum": 1, "description": "Optional maximum screenshot width in pixels."}}),
                idempotent=True,
                evidence_policy="screenshot",
            ),
            self._action("android_create_session", "Create an Android automation session.", visibility="lifecycle_only"),
            self._action("android_delete_session", "Delete the Android automation session.", visibility="lifecycle_only", idempotent=True),
            self._action("android_activate_app", "Activate the Android application under test.", visibility="lifecycle_only"),
            self._action("android_terminate_app", "Terminate the Android application under test.", visibility="lifecycle_only", idempotent=True),
            self._action("android_query_app_state", "Query Android application state.", visibility="lifecycle_only", idempotent=True),
            self._action("android_hide_keyboard", "Hide the Android soft keyboard.", visibility="lifecycle_only", idempotent=True),
            self._action("android_dismiss_alert", "Dismiss an Android alert.", visibility="lifecycle_only", idempotent=True),
        ]

    def _action(
        self,
        name: str,
        description: str,
        *,
        visibility: str = "agent_visible",
        idempotent: bool = False,
        evidence_policy: str = "default",
        input_schema: dict[str, Any] | None = None,
    ) -> PlatformActionDefinition:
        return PlatformActionDefinition(
            name=name,
            description=description,
            input_schema=input_schema or self._object_schema({}),
            visibility=visibility,  # type: ignore[arg-type]
            idempotent=idempotent,
            evidence_policy=evidence_policy,
        )

    def _object_schema(self, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": required or [],
            "additionalProperties": False,
        }

    def _locator_schema(self) -> dict[str, Any]:
        return {
            "strategy": {
                "type": "string",
                "enum": list(AndroidAppiumMCPBackend._LOCATOR_STRATEGIES),
                "description": "Appium locator strategy. Prefer accessibility id, then id, then -android uiautomator; use xpath only as a last resort.",
            },
            "selector": {"type": "string", "description": "Selector for the chosen strategy. Do not put natural-language descriptions here."},
        }

    def _element_reference_schema(self) -> dict[str, Any]:
        return {
            "element_id": {"type": "string", "description": "Element id returned by android_find_element or by a previous platform action output."},
            **self._locator_schema(),
            "target": {"type": "string", "description": "Convenience fallback: visible text, content description, resource id, xpath, or prefixed locator such as accessibilityId=Settings."},
        }

    def _drag_endpoint_schema(self, prefix: str) -> dict[str, Any]:
        return {
            f"{prefix}_element_id": {"type": "string", "description": f"Element id for the {prefix} endpoint."},
            f"{prefix}_strategy": {"type": "string", "enum": list(AndroidAppiumMCPBackend._LOCATOR_STRATEGIES), "description": f"Appium locator strategy for the {prefix} endpoint."},
            f"{prefix}_selector": {"type": "string", "description": f"Locator selector for the {prefix} endpoint."},
            f"{prefix}_target": {"type": "string", "description": f"Convenience fallback target for the {prefix} endpoint."},
            f"{prefix}_x": {"type": "integer", "minimum": 0, "description": f"Optional {prefix} X coordinate fallback. Requires {prefix}_y."},
            f"{prefix}_y": {"type": "integer", "minimum": 0, "description": f"Optional {prefix} Y coordinate fallback. Requires {prefix}_x."},
        }


class AndroidHarness(Harness):
    def __init__(
        self,
        adapter: AndroidAppiumPlatformAdapter,
        options: dict[str, Any] | None = None,
        event_sink: RunEventSink | None = None,
        run_id: str = "",
        task_id: str = "",
    ) -> None:
        super().__init__(adapter, event_sink=event_sink, run_id=run_id, task_id=task_id)
        self.android_adapter = adapter
        self.options = options or {}

    async def run_setup(self, context: dict[str, Any] | None = None) -> None:
        last_result: PlatformActionResult | None = None
        for attempt in range(1, self.android_adapter.settings.session_create_attempts + 1):
            result = await self.invoke_action("android_create_session", {"platform": "android"}, context)
            if result.status != "failed":
                return None
            last_result = result
            if attempt < self.android_adapter.settings.session_create_attempts and self.android_adapter.settings.session_create_retry_delay_seconds:
                await asyncio.sleep(self.android_adapter.settings.session_create_retry_delay_seconds)
        raise ToolExecutionError(
            "Android harness action failed: android_create_session",
            context={
                "action_name": "android_create_session",
                "failure_category": last_result.failure_category if last_result else "lifecycle_error",
                "error": last_result.error if last_result else None,
            },
        )

    async def run_teardown(self, context: dict[str, Any] | None = None) -> None:
        result = await self.invoke_action("android_delete_session", {}, context)
        if result.status == "failed":
            return None
        return None

    async def case_setup(self, task: Task, context: dict[str, Any] | None = None) -> None:
        app_id = self._require_app_id()
        if self.options.get("case_reset", "terminate_and_activate") == "terminate_and_activate":
            await self.invoke_action("android_terminate_app", {"app_id": app_id}, context)
        await self._require_success("android_activate_app", {"app_id": app_id}, context)
        await self._require_success("android_query_app_state", {"app_id": app_id}, context)

    async def case_teardown(self, task: Task, context: dict[str, Any] | None = None) -> None:
        app_id = self._require_app_id()
        cleanup = self.options.get("teardown_cleanup", {})
        if not isinstance(cleanup, dict):
            cleanup = {}
        if cleanup.get("hide_keyboard", True):
            await self.invoke_action("android_hide_keyboard", {}, context)
        if cleanup.get("dismiss_alert", True):
            await self.invoke_action("android_dismiss_alert", {}, context)
        if cleanup.get("terminate_app", True):
            await self.invoke_action("android_terminate_app", {"app_id": app_id}, context)

    def runtime_policy(self) -> list[str]:
        return [
            "Use FSQ Android platform actions such as android_tap, android_input_text, android_press_key, android_back, android_find_element, android_scroll_to_element, android_get_text, android_get_attribute, android_page_source, android_window_size, and android_screenshot for Android automation.",
            "Prefer exact element_id or strategy+selector arguments over broad target text. Use target only as a convenience fallback.",
            "Do not manage Android automation sessions directly; session and app lifecycle are harness responsibilities.",
        ]

    async def _require_success(
        self,
        action_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> PlatformActionResult:
        result = await self.invoke_action(action_name, params, context)
        if result.status == "failed":
            raise ToolExecutionError(
                f"Android harness action failed: {action_name}",
                context={"action_name": action_name, "failure_category": result.failure_category, "error": result.error},
            )
        return result

    def _require_app_id(self) -> str:
        app_id = self.android_adapter.app_id()
        if not app_id:
            raise ToolExecutionError(
                "Android harness requires appium:appPackage in the Appium capabilities file pointed to by the configured environment variable.",
                context={"platform": "android", "capabilities_config_env": self.android_adapter.settings.capabilities_config_env},
            )
        return app_id
