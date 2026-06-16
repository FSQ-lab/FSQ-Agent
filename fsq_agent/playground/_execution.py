from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
import threading
from typing import Callable

from fsq_agent.agent import FsqAgent
from fsq_agent.config import Settings, validate_runtime_settings
from fsq_agent.models import RunEvent, Task, TaskResult
from fsq_agent.playground._state import PlaygroundState
from fsq_agent.recording import StrictCaseRecording, record_dynamic_run_as_strict_case


def start_dynamic_goal_execution(
	*,
	settings: Settings,
	state: PlaygroundState,
	request_id: str,
	goal: str,
	device_id: str | None,
) -> threading.Thread:
	thread = threading.Thread(
		target=_run_dynamic_goal,
		kwargs={
			"settings": settings,
			"state": state,
			"request_id": request_id,
			"goal": goal,
			"device_id": device_id,
		},
		name=f"fsq-playground-{request_id}",
		daemon=True,
	)
	thread.start()
	return thread


def task_from_goal(goal: str) -> Task:
	normalized = " ".join(goal.split())
	slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "playground-goal"
	return Task(
		id=slug[:80],
		name=normalized,
		description=normalized,
		planning_reference_kind="goal",
		planning_reference_text=normalized,
	)


def _run_dynamic_goal(
	*,
	settings: Settings,
	state: PlaygroundState,
	request_id: str,
	goal: str,
	device_id: str | None,
) -> None:
	run_settings = settings.model_copy(deep=True)
	if device_id:
		run_settings.harness.android.serial = device_id
	try:
		validate_runtime_settings(run_settings)
		task = task_from_goal(goal)
		result = asyncio.run(
			FsqAgent.from_settings(run_settings).run(
				task,
				event_sink=_event_sink(state, request_id),
			)
		)
		state.finish_task(request_id, result, recording=_record_dynamic_result(run_settings, task, result))
	except BaseException as exc:  # noqa: BLE001 - background failures must be visible through progress state.
		state.fail_task(request_id, exc)


def _event_sink(state: PlaygroundState, request_id: str) -> Callable[[RunEvent], None]:
	def sink(event: RunEvent) -> None:
		state.add_event(request_id, event)

	return sink


def _record_dynamic_result(settings: Settings, task: Task, result: TaskResult) -> dict[str, object]:
	run_dir = Path(settings.output.runs_dir) / result.report.run_id
	try:
		recording = record_dynamic_run_as_strict_case(
			run_dir=run_dir,
			task=task,
			result=result,
			settings=settings,
			allow_failure=True,
		)
		return recording.to_json()
	except Exception as exc:  # noqa: BLE001 - recording must not change dynamic run status.
		recording_path = run_dir / "recording.json"
		recording = StrictCaseRecording(status="failed", recording_path=recording_path, errors=[str(exc)])
		try:
			recording_path.parent.mkdir(parents=True, exist_ok=True)
			recording_path.write_text(json.dumps(recording.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")
		except OSError:
			pass
		return recording.to_json()
