from auto_test_agent.models import ExecutionStep, ObservationError, StepResult
from auto_test_agent.observation._logger import ExecutionLogger
from auto_test_agent.observation._screenshot import ScreenCapture
from auto_test_agent.observation._ui_tree import UITreeExtractor


class ObservationRecorder:
    def __init__(
        self,
        screen_capture: ScreenCapture,
        ui_tree_extractor: UITreeExtractor,
        logger: ExecutionLogger,
    ) -> None:
        self.screen_capture = screen_capture
        self.ui_tree_extractor = ui_tree_extractor
        self.logger = logger

    def record_step(self, run_id: str, step: ExecutionStep, result: StepResult) -> StepResult:
        diagnostics = []
        if result.screenshot_path is None:
            try:
                result.screenshot_path = self.screen_capture.capture(run_id, step.step_id)
            except ObservationError as exc:
                diagnostics.append(str(exc))
        if result.ui_tree_snapshot is None:
            result.ui_tree_snapshot = self.ui_tree_extractor.extract()
        payload = {
            "step": step.model_dump(mode="json"),
            "result": result.model_dump(mode="json"),
            "observation_warnings": diagnostics,
        }
        self.logger.write_event(run_id, "step_recorded", payload)
        return result