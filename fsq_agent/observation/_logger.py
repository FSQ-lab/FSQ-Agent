import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ExecutionLogger:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def write_event(self, run_id: str, event: str, payload: dict[str, Any]) -> None:
        path = self.logs_dir / f"{run_id}.jsonl"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "event": event,
            "payload": payload,
        }
        with path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")