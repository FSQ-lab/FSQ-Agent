from typing import Any

import pytest

from fsq_agent.core import AndroidHarness, ArtifactStore, HarnessInterface
from fsq_agent.models import ExecutableStep, HarnessContext


class FakeAndroidDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def context(self) -> dict[str, object]:
        self.calls.append(("context", None))
        return {
            "session_id": "android-session-1",
            "current_activity": "MainActivity",
            "screen_size": (1080, 2400),
        }

    def tap(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("tap", params))
        return {"tapped": True}

    def input_text(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("input_text", params))
        return {"input": True}

    def back(self) -> dict[str, object]:
        self.calls.append(("back", None))
        return {"back": True}

    def screenshot(self) -> bytes:
        self.calls.append(("screenshot", None))
        return b"fake-png"

    def ui_tree(self) -> dict[str, object]:
        self.calls.append(("ui_tree", None))
        return {"nodes": [{"text": "Login"}]}


def _step(action_name: str, params: dict[str, Any] | None = None) -> ExecutableStep:
    return ExecutableStep(
        step_id="step-1",
        kind="action",
        action_name=action_name,
        params=params or {},
    )


def test_android_harness_dispatches_tap_to_driver() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)

    context = harness.get_context()
    result = harness.invoke_action(_step("tap", {"x": 10, "y": 20}), context)

    assert isinstance(harness, HarnessInterface)
    assert context == HarnessContext(
        platform="android",
        session_id="android-session-1",
        current_activity="MainActivity",
        screen_size=(1080, 2400),
    )
    assert result.status == "passed"
    assert result.action_name == "tap"
    assert result.output == {"tapped": True}
    assert driver.calls == [
        ("context", None),
        ("tap", {"x": 10, "y": 20}),
    ]


def test_android_harness_dispatches_input_text_and_back_to_driver() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)
    context = harness.get_context()

    input_result = harness.invoke_action(_step("inputText", {"text": "hello"}), context)
    back_result = harness.invoke_action(_step("back"), context)

    assert input_result.status == "passed"
    assert input_result.output == {"input": True}
    assert back_result.status == "passed"
    assert back_result.output == {"back": True}
    assert driver.calls == [
        ("context", None),
        ("input_text", {"text": "hello"}),
        ("back", None),
    ]


def test_android_harness_returns_failed_result_for_unsupported_action() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)

    result = harness.invoke_action(_step("swipe", {"direction": "up"}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert result.error_message == "Unsupported Android action: swipe"
    assert driver.calls == [("context", None)]


def test_android_harness_captures_screenshot_and_ui_tree_with_artifact_store(tmp_path) -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver, artifact_store=ArtifactStore(run_dir=tmp_path))
    context = harness.get_context()

    screenshot_ref = harness.capture_artifact("screenshot", "after tap", context)
    ui_tree_ref = harness.capture_artifact("ui_tree", "after tap", context)

    assert screenshot_ref.path.as_posix() == "artifacts/screenshots/android-session-1-finalize-after-tap.png"
    assert (tmp_path / screenshot_ref.path).read_bytes() == b"fake-png"
    assert ui_tree_ref.path.as_posix() == "artifacts/ui-trees/android-session-1-finalize-after-tap.json"
    assert "Login" in (tmp_path / ui_tree_ref.path).read_text(encoding="utf-8")
    assert driver.calls == [
        ("context", None),
        ("screenshot", None),
        ("ui_tree", None),
    ]


def test_android_harness_requires_artifact_store_for_capture() -> None:
    harness = AndroidHarness(driver=FakeAndroidDriver())

    with pytest.raises(RuntimeError, match="Artifact capture requires an ArtifactStore"):
        harness.capture_artifact("screenshot", "after tap", harness.get_context())
