from pathlib import Path

from auto_test_agent.models import ObservationError, ObservationSettings


class ScreenCapture:
    def __init__(self, settings: ObservationSettings, output_dir: Path) -> None:
        self.settings = settings
        self.output_dir = output_dir

    def capture(self, run_id: str, step_id: int) -> Path | None:
        if not self.settings.screenshot.enabled:
            return None
        path = self.output_dir / run_id / f"step-{step_id}.{self.settings.screenshot.format}"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import mss
            import mss.tools

            with mss.mss() as screen_capture:
                monitor = screen_capture.monitors[0]
                image = screen_capture.grab(monitor)
                mss.tools.to_png(image.rgb, image.size, output=str(path))
        except Exception as exc:
            raise ObservationError("Screenshot capture failed.", context={"path": str(path)}) from exc
        return path