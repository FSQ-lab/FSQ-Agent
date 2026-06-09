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
        return {
            "tap": {"description": "Tap an Android target."},
            "inputText": {"description": "Input text into an Android target."},
            "back": {"description": "Press Android back."},
        }

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        return None

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        if step.action_name == "tap":
            output = self.driver.tap(step.params)
            return HarnessActionResult(status="passed", action_name=step.action_name, output=output)
        if step.action_name == "inputText":
            output = self.driver.input_text(step.params)
            return HarnessActionResult(status="passed", action_name=step.action_name, output=output)
        if step.action_name == "back":
            output = self.driver.back()
            return HarnessActionResult(status="passed", action_name=step.action_name, output=output)
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

    def capture_artifact(self, kind: str, reason: str, context: HarnessContext) -> HarnessArtifactRef:
        if self.artifact_store is None:
            raise RuntimeError("Artifact capture requires an ArtifactStore.")
        step_id = context.session_id or "android"
        if kind == "screenshot":
            return self.artifact_store.write_bytes(
                kind="screenshot",
                step_id=step_id,
                phase="finalize",
                name=reason,
                data=self.driver.screenshot(),
            )
        if kind == "ui_tree":
            return self.artifact_store.write_json(
                kind="ui_tree",
                step_id=step_id,
                phase="finalize",
                name=reason,
                payload=self.driver.ui_tree(),
            )
        raise RuntimeError(f"Unsupported Android artifact kind: {kind}")

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        return "harness_error"

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
