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

    def launch_app(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("launch_app", params))
        return {"launched": True}

    def kill_app(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("kill_app", params))
        return {"killed": True}

    def tap_on(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("tap_on", params))
        return {"tapped": True}

    def long_press_on(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("long_press_on", params))
        return {"long_pressed": True}

    def input_text(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("input_text", params))
        return {"input": True}

    def press_key(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("press_key", params))
        return {"pressed": True}

    def swipe(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("swipe", params))
        return {"swiped": True}

    def perform_actions(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("perform_actions", params))
        return {"performed": True}

    def assert_visible(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("assert_visible", params))
        return {"visible": True}

    def assert_not_visible(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("assert_not_visible", params))
        return {"not_visible": True}

    def assert_state(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("assert_state", params))
        return {"asserted": True}

    def assert_with_ai(self, params: dict[str, object]) -> dict[str, object]:
        self.calls.append(("assert_with_ai", params))
        return {"ai_asserted": True}

    def screenshot(self) -> bytes:
        self.calls.append(("screenshot", None))
        return b"fake-png"

    def ui_tree(self) -> dict[str, object]:
        self.calls.append(("ui_tree", None))
        return {"nodes": [{"text": "Login"}]}


class FakeAIAssertionEvaluator:
    def __init__(self, verdict: str = "passed") -> None:
        self.verdict = verdict
        self.calls: list[dict[str, object]] = []

    def evaluate(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(dict(kwargs))
        return {"verdict": self.verdict, "reasoning": "visual assertion matched"}


def _step(action_name: str, params: dict[str, Any] | None = None) -> ExecutableStep:
    return ExecutableStep(
        step_id="step-1",
        kind="action",
        action_name=action_name,
        params=params or {},
    )


def test_android_harness_dispatches_fsq_action_names_to_driver() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)

    context = harness.get_context()

    cases = [
        ("launchApp", {}, "launch_app"),
        ("killApp", {}, "kill_app"),
        ("tapOn", {"target": "Menu"}, "tap_on"),
        ("assertVisible", {"target": "Menu"}, "assert_visible"),
        ("inputText", {"text": "bing.com"}, "input_text"),
        ("longPressOn", {"target": "Address bar"}, "long_press_on"),
        ("swipe", {"direction": "up", "duration": 1000}, "swipe"),
        ("assertNotVisible", {"target": "Dialog"}, "assert_not_visible"),
        ("assert", {"text": {"contains": "bing.com"}}, "assert_state"),
    ]

    for action_name, params, _method_name in cases:
        result = harness.invoke_action(_step(action_name, params), context)
        assert result.status == "passed"
        assert result.action_name == action_name

    assert isinstance(harness, HarnessInterface)
    assert context == HarnessContext(
        platform="android",
        session_id="android-session-1",
        current_activity="MainActivity",
        screen_size=(1080, 2400),
    )
    assert driver.calls == [("context", None)] + [
        (method_name, params) for _action_name, params, method_name in cases
    ]


def test_android_harness_normalizes_press_key_string_shorthand() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)

    result = harness.invoke_action(_step("pressKey", {"value": "Back"}), harness.get_context())

    assert result.status == "passed"
    assert driver.calls[-1] == ("press_key", {"key": "Back"})


def test_android_harness_wraps_perform_actions_list() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)
    actions = [{"type": "none", "id": "wait", "actions": [{"type": "pause", "duration": 1}]}]

    result = harness.invoke_action(_step("performActions", {"value": actions}), harness.get_context())

    assert result.status == "passed"
    assert driver.calls[-1] == ("perform_actions", {"actions": actions})


def test_android_harness_converts_driver_failure_result() -> None:
    class FailingDriver(FakeAndroidDriver):
        def tap_on(self, params: dict[str, object]) -> dict[str, object]:
            self.calls.append(("tap_on", params))
            return {
                "status": "failed",
                "output": {"matched": False},
                "error_message": "Target was not found.",
                "failure_category": "target_resolution_error",
                "metadata": {"backend": "fake"},
            }

    driver = FailingDriver()
    harness = AndroidHarness(driver=driver)

    result = harness.invoke_action(_step("tapOn", {"target": "Missing"}), harness.get_context())

    assert result.status == "failed"
    assert result.action_name == "tapOn"
    assert result.output == {"matched": False}
    assert result.error_message == "Target was not found."
    assert result.failure_category == "target_resolution_error"
    assert result.metadata == {"backend": "fake"}


def test_android_harness_returns_failed_result_for_unsupported_action() -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver)

    result = harness.invoke_action(_step("doubleTapOn", {"target": "Menu"}), harness.get_context())

    assert result.status == "failed"
    assert result.failure_category == "configuration_error"
    assert result.error_message == "Unsupported Android action: doubleTapOn"
    assert driver.calls == [("context", None)]


def test_android_harness_captures_screenshot_and_ui_tree_with_artifact_store(tmp_path) -> None:
    driver = FakeAndroidDriver()
    harness = AndroidHarness(driver=driver, artifact_store=ArtifactStore(run_dir=tmp_path))
    context = harness.get_context()

    screenshot_ref = harness.capture_artifact(
        kind="screenshot",
        reason="after tap",
        context=context,
        step_id="step-1",
        phase="invoke",
    )
    ui_tree_ref = harness.capture_artifact(
        kind="ui_tree",
        reason="after tap",
        context=context,
        step_id="step-1",
        phase="finalize",
    )

    assert screenshot_ref.path.as_posix() == "artifacts/screenshots/step-1-invoke-after-tap.png"
    assert (tmp_path / screenshot_ref.path).read_bytes() == b"fake-png"
    assert ui_tree_ref.path.as_posix() == "artifacts/ui-trees/step-1-finalize-after-tap.json"
    assert "Login" in (tmp_path / ui_tree_ref.path).read_text(encoding="utf-8")
    assert driver.calls == [
        ("context", None),
        ("screenshot", None),
        ("ui_tree", None),
    ]


def test_android_harness_assert_with_ai_uses_injected_evaluator_and_artifacts(tmp_path) -> None:
    driver = FakeAndroidDriver()
    evaluator = FakeAIAssertionEvaluator()
    harness = AndroidHarness(
        driver=driver,
        artifact_store=ArtifactStore(run_dir=tmp_path),
        ai_assertion_evaluator=evaluator,
    )
    context = harness.get_context()

    result = harness.invoke_action(_step("assertWithAI", {"prompt": "Verify Bing homepage"}), context)

    assert result.status == "passed"
    assert result.action_name == "assertWithAI"
    assert result.output == {"verdict": "passed", "reasoning": "visual assertion matched"}
    assert result.metadata["assertion_engine"] == "ai_visual"
    assert result.metadata["prompt"] == "Verify Bing homepage"
    assert result.metadata["verdict"] == "passed"
    assert [ref.kind for ref in result.artifact_refs] == ["screenshot", "ui_tree"]
    assert (tmp_path / result.artifact_refs[0].path).read_bytes() == b"fake-png"
    assert "Login" in (tmp_path / result.artifact_refs[1].path).read_text(encoding="utf-8")
    assert evaluator.calls[0]["prompt"] == "Verify Bing homepage"
    assert evaluator.calls[0]["screenshot"] == b"fake-png"
    assert evaluator.calls[0]["ui_tree"] == {"nodes": [{"text": "Login"}]}
    assert driver.calls == [
        ("context", None),
        ("screenshot", None),
        ("ui_tree", None),
    ]


def test_android_harness_assert_with_ai_requires_evaluator_and_artifact_store(tmp_path) -> None:
    driver = FakeAndroidDriver()
    context = AndroidHarness(driver=driver).get_context()

    no_evaluator = AndroidHarness(driver=driver, artifact_store=ArtifactStore(run_dir=tmp_path)).invoke_action(
        _step("assertWithAI", {"prompt": "Verify Bing"}),
        context,
    )
    no_store = AndroidHarness(driver=driver, ai_assertion_evaluator=FakeAIAssertionEvaluator()).invoke_action(
        _step("assertWithAI", {"prompt": "Verify Bing"}),
        context,
    )

    assert no_evaluator.status == "failed"
    assert no_evaluator.failure_category == "configuration_error"
    assert "AI assertion evaluator" in no_evaluator.error_message
    assert no_store.status == "failed"
    assert no_store.failure_category == "configuration_error"
    assert "ArtifactStore" in no_store.error_message


def test_android_harness_requires_artifact_store_for_capture() -> None:
    harness = AndroidHarness(driver=FakeAndroidDriver())

    with pytest.raises(RuntimeError, match="Artifact capture requires an ArtifactStore"):
        harness.capture_artifact(
            kind="screenshot",
            reason="after tap",
            context=harness.get_context(),
            step_id="step-1",
            phase="finalize",
        )
