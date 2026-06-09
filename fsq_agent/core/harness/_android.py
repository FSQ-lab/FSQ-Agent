from fsq_agent.core.evidence import ArtifactStore
from fsq_agent.core.harness._android_driver import AndroidDriverInterface
from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    StepPhase,
)


class AndroidHarness:
    _RUNNER_STATUSES = {"passed", "failed", "skipped", "cancelled"}
    _FAILURE_CATEGORIES = {
        "configuration_error",
        "context_error",
        "target_resolution_error",
        "action_error",
        "assertion_error",
        "timeout_error",
        "observation_error",
        "artifact_error",
        "harness_error",
        "cancelled",
        "unknown",
    }
    _ACTION_METHODS = {
        "launchApp": "launch_app",
        "killApp": "kill_app",
        "tapOn": "tap_on",
        "assertVisible": "assert_visible",
        "performActions": "perform_actions",
        "assert": "assert_state",
        "pressKey": "press_key",
        "inputText": "input_text",
        "assertNotVisible": "assert_not_visible",
        "longPressOn": "long_press_on",
        "swipe": "swipe",
        "assertWithAI": "assert_with_ai",
    }

    def __init__(self, driver: AndroidDriverInterface, artifact_store: ArtifactStore | None = None) -> None:
        self.driver = driver
        self.artifact_store = artifact_store

    def get_context(self) -> HarnessContext:
        context = self.driver.context()
        return HarnessContext(
            platform="android",
            session_id=self._optional_str(context.get("session_id")),
            current_activity=self._optional_str(context.get("current_activity")),
            screen_size=self._screen_size(context.get("screen_size")),
            capabilities=self._dict_value(context.get("capabilities")),
            metadata=self._dict_value(context.get("metadata")),
        )

    def action_space(self) -> dict[str, object]:
        return {action_name: {"driver_method": method_name} for action_name, method_name in self._ACTION_METHODS.items()}

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        return None

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        method_name = self._ACTION_METHODS.get(step.action_name)
        if method_name is not None:
            driver_method = getattr(self.driver, method_name)
            output = driver_method(self._normalize_params(step))
            return self._result_from_driver_output(step.action_name, output)
        return HarnessActionResult(
            status="failed",
            action_name=step.action_name,
            failure_category="configuration_error",
            error_message=f"Unsupported Android action: {step.action_name}",
        )

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult | None,
    ) -> None:
        return None

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        if self.artifact_store is None:
            raise RuntimeError("Artifact capture requires an ArtifactStore.")
        if kind == "screenshot":
            return self.artifact_store.write_bytes(
                kind="screenshot",
                step_id=step_id,
                phase=phase,
                name=reason,
                data=self.driver.screenshot(),
            )
        if kind == "ui_tree":
            return self.artifact_store.write_json(
                kind="ui_tree",
                step_id=step_id,
                phase=phase,
                name=reason,
                payload=self.driver.ui_tree(),
            )
        raise RuntimeError(f"Unsupported Android artifact kind: {kind}")

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        return "harness_error"

    def _normalize_params(self, step: ExecutableStep) -> dict[str, object]:
        if step.action_name in {"launchApp", "killApp"}:
            return {}
        if step.action_name == "pressKey" and "value" in step.params:
            return {"key": step.params["value"]}
        if step.action_name == "performActions" and "value" in step.params:
            return {"actions": step.params["value"]}
        return step.params

    def _result_from_driver_output(self, action_name: str, output: object) -> HarnessActionResult:
        if not isinstance(output, dict) or "status" not in output:
            return HarnessActionResult(status="passed", action_name=action_name, output=output)

        status_value = output.get("status")
        status = status_value if isinstance(status_value, str) and status_value in self._RUNNER_STATUSES else "passed"

        failure_category_value = output.get("failure_category")
        failure_category = (
            failure_category_value
            if isinstance(failure_category_value, str) and failure_category_value in self._FAILURE_CATEGORIES
            else None
        )
        error_message_value = output.get("error_message")
        metadata_value = output.get("metadata")

        return HarnessActionResult(
            status=status,
            action_name=action_name,
            output=output.get("output"),
            error_message=error_message_value if isinstance(error_message_value, str) else None,
            failure_category=failure_category,
            metadata=metadata_value if isinstance(metadata_value, dict) else {},
        )

    def _optional_str(self, value: object) -> str | None:
        return value if isinstance(value, str) else None

    def _screen_size(self, value: object) -> tuple[int, int] | None:
        if not isinstance(value, tuple) or len(value) != 2:
            return None
        width, height = value
        if not isinstance(width, int) or not isinstance(height, int):
            return None
        return (width, height)

    def _dict_value(self, value: object) -> dict[str, object]:
        return value if isinstance(value, dict) else {}
