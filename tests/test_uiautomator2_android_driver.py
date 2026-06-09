import builtins
from typing import Any

import pytest

from fsq_agent.core import AndroidDriverInterface, UiAutomator2AndroidDriver
from fsq_agent.models import ConfigurationError


class FakeSelector:
    def __init__(self, device: "FakeDevice", query: dict[str, object], exists: bool | None = None) -> None:
        self.device = device
        self.query = query
        self.exists = device.exists if exists is None else exists

    def click(self) -> None:
        self.device.calls.append(("click", self.query))

    def long_click(self) -> None:
        self.device.calls.append(("long_click", self.query))

    def set_text(self, text: str) -> None:
        self.device.calls.append(("set_text", self.query, text))

    def get_text(self) -> str:
        self.device.calls.append(("get_text", self.query))
        return self.device.text


class FakeDevice:
    def __init__(self, *, exists: bool = True, text: str = "Loaded") -> None:
        self.exists = exists
        self.text = text
        self.calls: list[tuple[Any, ...]] = []
        self.info = {
            "displayWidth": 1080,
            "displayHeight": 2400,
            "currentPackageName": "com.example.app",
        }

    def __call__(self, **query: object) -> FakeSelector:
        self.calls.append(("select", query))
        return FakeSelector(self, query)

    def xpath(self, value: str) -> FakeSelector:
        self.calls.append(("xpath", value))
        return FakeSelector(self, {"xpath": value})

    def app_start(self, app_id: str, **options: object) -> None:
        self.calls.append(("app_start", app_id, options))

    def app_stop(self, app_id: str) -> None:
        self.calls.append(("app_stop", app_id))

    def press(self, key: str) -> None:
        self.calls.append(("press", key))

    def swipe(self, sx: int, sy: int, ex: int, ey: int, duration: float) -> None:
        self.calls.append(("swipe", sx, sy, ex, ey, duration))

    def screenshot(self, format: str = "raw") -> bytes:
        self.calls.append(("screenshot", format))
        return b"fake-png"

    def dump_hierarchy(self) -> str:
        self.calls.append(("dump_hierarchy",))
        return "<hierarchy />"


def test_uiautomator2_driver_context_launch_kill_and_artifacts() -> None:
    device = FakeDevice()
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    context = driver.context()

    assert isinstance(driver, AndroidDriverInterface)
    assert context["session_id"] == "uiautomator2:fake-device"
    assert context["screen_size"] == (1080, 2400)
    assert driver.launch_app({})["status"] == "passed"
    assert driver.kill_app({})["status"] == "passed"
    assert driver.screenshot() == b"fake-png"
    assert driver.ui_tree() == {"xml": "<hierarchy />"}
    assert device.calls == [
        ("app_start", "com.example.app", {}),
        ("app_stop", "com.example.app"),
        ("screenshot", "raw"),
        ("dump_hierarchy",),
    ]


def test_uiautomator2_driver_actions_use_locator_selectors() -> None:
    device = FakeDevice(text="bing.com")
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    assert driver.tap_on({"locator": {"resourceId": "login"}})["status"] == "passed"
    assert driver.long_press_on({"locator": {"accessibilityId": "Menu"}})["status"] == "passed"
    assert driver.input_text({"text": "hello", "locator": {"text": "Search"}})["status"] == "passed"
    assert driver.press_key({"key": "Back"})["status"] == "passed"
    assert driver.swipe({"direction": "up", "duration": 100})["status"] == "passed"
    assert driver.assert_state({"element": {"resourceId": "url"}, "text": {"contains": "bing"}})["status"] == "passed"

    assert device.calls[:7] == [
        ("select", {"resourceId": "login"}),
        ("click", {"resourceId": "login"}),
        ("select", {"description": "Menu"}),
        ("long_click", {"description": "Menu"}),
        ("select", {"text": "Search"}),
        ("set_text", {"text": "Search"}, "hello"),
        ("press", "back"),
    ]


def test_uiautomator2_driver_assertion_and_missing_target_results() -> None:
    device = FakeDevice(exists=False)
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=device)

    missing = driver.assert_visible({"locator": {"text": "Missing"}})
    absent = driver.assert_not_visible({"locator": {"text": "Missing"}})

    assert missing["status"] == "failed"
    assert missing["failure_category"] == "target_resolution_error"
    assert absent["status"] == "passed"


def test_uiautomator2_driver_reports_unimplemented_backend_operations() -> None:
    driver = UiAutomator2AndroidDriver(app_id="com.example.app", device=FakeDevice())

    perform_result = driver.perform_actions({"actions": []})
    ai_result = driver.assert_with_ai({"prompt": "Verify page"})

    assert perform_result["status"] == "failed"
    assert perform_result["failure_category"] == "configuration_error"
    assert ai_result["status"] == "failed"
    assert ai_result["failure_category"] == "configuration_error"


def test_uiautomator2_driver_raises_configuration_error_when_dependency_missing(monkeypatch) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "uiautomator2":
            raise ImportError("missing uiautomator2")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ConfigurationError) as exc_info:
        UiAutomator2AndroidDriver(app_id="com.example.app")

    assert exc_info.value.context == {"install": "pip install fsq-agent[android]"}
