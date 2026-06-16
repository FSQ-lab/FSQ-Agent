from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Literal
from uuid import uuid4

from fsq_agent.models import RunEvent, TaskResult


TaskProgressStatus = Literal["running", "success", "failed", "inconclusive", "error"]


def _utc_now() -> str:
	return datetime.now(timezone.utc).isoformat()


@dataclass
class PlaygroundSession:
	connected: bool = False
	device_id: str | None = None
	display_name: str | None = None
	metadata: dict[str, object] = field(default_factory=dict)

	def to_json(self) -> dict[str, object]:
		return {
			"connected": self.connected,
			"deviceId": self.device_id,
			"displayName": self.display_name,
			"metadata": self.metadata,
		}


@dataclass
class TaskProgress:
	request_id: str
	goal: str
	status: TaskProgressStatus = "running"
	started_at: str = field(default_factory=_utc_now)
	completed_at: str | None = None
	events: list[dict[str, object]] = field(default_factory=list)
	result: dict[str, object] | None = None
	error: str | None = None

	def to_json(self) -> dict[str, object]:
		return {
			"requestId": self.request_id,
			"goal": self.goal,
			"status": self.status,
			"startedAt": self.started_at,
			"completedAt": self.completed_at,
			"events": self.events,
			"result": self.result,
			"error": self.error,
		}


class PlaygroundState:
	def __init__(self) -> None:
		self._lock = Lock()
		self.server_id = str(uuid4())
		self.session = PlaygroundSession()
		self.current_request_id: str | None = None
		self.tasks: dict[str, TaskProgress] = {}
		self.last_run: dict[str, object] | None = None

	def status(self) -> dict[str, object]:
		with self._lock:
			return {
				"status": "ok",
				"id": self.server_id,
				"busy": self.current_request_id is not None,
				"session": self.session.to_json(),
				"lastRun": self.last_run,
			}

	def create_session(self, device_id: str) -> dict[str, object]:
		with self._lock:
			if self.current_request_id:
				raise BusyError("Cannot replace session while a task is running.")
			normalized = device_id.strip()
			self.session = PlaygroundSession(
				connected=True,
				device_id=normalized,
				display_name=normalized,
				metadata={"platform": "android"},
			)
			return self.session.to_json()

	def destroy_session(self) -> dict[str, object]:
		with self._lock:
			if self.current_request_id:
				raise BusyError("Cannot destroy session while a task is running.")
			self.session = PlaygroundSession()
			return self.session.to_json()

	def start_task(self, goal: str) -> str:
		with self._lock:
			if self.current_request_id:
				raise BusyError("Another task is already running.")
			request_id = str(uuid4())
			self.current_request_id = request_id
			self.tasks[request_id] = TaskProgress(request_id=request_id, goal=goal)
			return request_id

	def add_event(self, request_id: str, event: RunEvent) -> None:
		with self._lock:
			task = self.tasks.get(request_id)
			if task is None:
				return
			task.events.append(event.model_dump(mode="json"))

	def finish_task(self, request_id: str, result: TaskResult, recording: dict[str, object] | None = None) -> None:
		with self._lock:
			task = self.tasks[request_id]
			task.status = result.status
			task.completed_at = _utc_now()
			task.result = {
				"taskId": result.task_id,
				"status": result.status,
				"summary": result.verification.summary,
				"runId": result.report.run_id,
				"reportPath": str(result.report.path),
				"durationMs": result.duration_ms,
				"recording": recording,
			}
			self.last_run = task.result
			if self.current_request_id == request_id:
				self.current_request_id = None

	def fail_task(self, request_id: str, error: BaseException | str) -> None:
		with self._lock:
			task = self.tasks.get(request_id)
			if task is not None:
				task.status = "error"
				task.completed_at = _utc_now()
				task.error = str(error) or error.__class__.__name__ if isinstance(error, BaseException) else str(error)
			if self.current_request_id == request_id:
				self.current_request_id = None

	def get_task(self, request_id: str) -> dict[str, object] | None:
		with self._lock:
			task = self.tasks.get(request_id)
			return task.to_json() if task else None


class BusyError(RuntimeError):
	pass
