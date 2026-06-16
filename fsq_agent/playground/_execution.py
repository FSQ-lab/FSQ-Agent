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
	goal: str | None = None,
	case_yaml_path: str | None = None,
	device_id: str | None,
) -> threading.Thread:
	thread = threading.Thread(
		target=_run_dynamic_task,
		kwargs={
			"settings": settings,
			"state": state,
			"request_id": request_id,
			"goal": goal,
			"case_yaml_path": case_yaml_path,
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


def task_from_case_yaml(path_text: str, settings: Settings) -> Task:
	source_path, content = _read_case_yaml_text(path_text, settings)
	display_path = str(source_path)
	name = f"Case reference: {source_path.name}"
	description = (
		"Run this raw FSQ YAML reference through dynamic LLM execution.\n\n"
		"The playground has not parsed this YAML into strict executable steps. "
		"Treat the full file content as advisory planning reference material.\n\n"
		f"Source path: {display_path}\n\n"
		"Raw file content:\n"
		f"{content}"
	)
	reference_text = f"Source path: {display_path}\n\nRaw file content:\n{content}"
	slug_source = source_path.stem or "case-yaml"
	slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-") or "case-yaml"
	return Task(
		id=slug[:80],
		name=name,
		description=description,
		planning_reference_kind="raw_case",
		planning_reference_text=reference_text,
	)


def _read_case_yaml_text(path_text: str, settings: Settings) -> tuple[Path, str]:
	requested = Path(path_text.strip())
	candidates = []
	if requested.is_absolute():
		candidates.append(requested)
	else:
		candidates.append(settings.cases.dir / requested)
		candidates.append(Path.cwd() / requested)
	for candidate in candidates:
		if candidate.exists() and candidate.is_file():
			resolved = candidate.resolve()
			return resolved, resolved.read_text(encoding="utf-8")
	raise FileNotFoundError(f"Case YAML not found: {path_text}")


def _run_dynamic_task(
	*,
	settings: Settings,
	state: PlaygroundState,
	request_id: str,
	goal: str | None,
	case_yaml_path: str | None,
	device_id: str | None,
) -> None:
	run_settings = settings.model_copy(deep=True)
	if device_id:
		run_settings.harness.android.serial = device_id
	try:
		validate_runtime_settings(run_settings)
		if goal:
			task = task_from_goal(goal)
		elif case_yaml_path:
			task = task_from_case_yaml(case_yaml_path, run_settings)
		else:
			raise ValueError("goal or case_yaml_path is required")
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
