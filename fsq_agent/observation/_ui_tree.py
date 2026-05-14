import platform
from typing import Any

from fsq_agent.models import ObservationSettings


class UITreeExtractor:
    def __init__(self, settings: ObservationSettings) -> None:
        self.settings = settings

    def extract(self) -> dict[str, Any] | None:
        if not self.settings.ui_tree.enabled:
            return None
        if platform.system() != "Windows":
            return {"platform": platform.system(), "available": False, "reason": "UI tree extraction is Windows-first."}
        try:
            from pywinauto import Desktop

            windows = []
            for window in Desktop(backend="uia").windows()[:20]:
                windows.append({"title": window.window_text(), "class_name": window.class_name()})
            return {"platform": "Windows", "available": True, "windows": windows}
        except Exception as exc:
            return {"platform": "Windows", "available": False, "reason": str(exc)}