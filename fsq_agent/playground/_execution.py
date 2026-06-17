from __future__ import annotations

import asyncio
import os
import json
from pathlib import Path
import re
import threading
from typing import Any, Callable

from pydantic import ValidationError

from fsq_agent.agent import FsqAgent
from fsq_agent.config import Settings, validate_runtime_settings, validate_strict_core_settings
from fsq_agent.core import AndroidHarness, ArtifactStore, EvidenceRecorder, StepSequenceRunner, UiAutomator2AndroidDriver
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import ANDROID_ACTION_DEFINITIONS_BY_NAME, ExecutableStep, ReportArtifact, RunEvent, RuntimeSecretRef, Task, TaskResult, VerificationResult
from fsq_agent.playground._state import PlaygroundState
from fsq_agent.providers import build_ai_assertion_evaluator
from fsq_agent.report import CoreEvidenceReportGenerator
from fsq_agent.recording import StrictCaseRecording, record_dynamic_run_as_strict_case


def start_dynamic_goal_execution(
	*,
	settings: Settings,
	state: PlaygroundState,
	request_id: str,
	goal: str | None = None,
	case_yaml_path: str | None = None,
	strict_case_yaml_path: str | None = None,
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
			"strict_case_yaml_path": strict_case_yaml_path,
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
	strict_case_yaml_path: str | None,
	device_id: str | None,
) -> None:
	run_settings = settings.model_copy(deep=True)
	if device_id:
		run_settings.harness.android.serial = device_id
	try:
		if goal:
			validate_runtime_settings(run_settings)
			task = task_from_goal(goal)
			result = _run_agent_task(run_settings, state, request_id, task)
		elif case_yaml_path:
			validate_runtime_settings(run_settings)
			task = task_from_case_yaml(case_yaml_path, run_settings)
			result = _run_agent_task(run_settings, state, request_id, task)
		elif strict_case_yaml_path:
			result = _run_strict_case_yaml(run_settings, state, request_id, strict_case_yaml_path)
		else:
			raise ValueError("goal, case_yaml_path, or strict_case_yaml_path is required")
		state.finish_task(request_id, result, recording=None if strict_case_yaml_path else _record_dynamic_result(run_settings, task, result))
	except BaseException as exc:  # noqa: BLE001 - background failures must be visible through progress state.
		state.fail_task(request_id, exc)


def _run_agent_task(settings: Settings, state: PlaygroundState, request_id: str, task: Task) -> TaskResult:
	return asyncio.run(
		FsqAgent.from_settings(settings).run(
			task,
			event_sink=_event_sink(state, request_id),
		)
	)


def _run_strict_case_yaml(settings: Settings, state: PlaygroundState, request_id: str, path_text: str) -> TaskResult:
	case_path = _resolve_case_yaml_path(path_text, settings)
	case = FsqCaseLoader().load_case(case_path)
	requires_ai_assertion = _case_requires_ai_assertion(case)
	validate_strict_core_settings(settings, requires_ai_assertion=requires_ai_assertion)
	app_id = settings.harness.android.app_id or case.config.app_id or ""
	if not app_id:
		raise ValueError("Android app id is required for strict YAML runs.")
	run_id = case.id
	run_dir = Path(settings.output.runs_dir) / run_id
	state.add_event(
		request_id,
		RunEvent(run_id=run_id, task_id=case.id, type="run_started", title="Strict YAML started", message=str(case_path)),
	)
	steps = _resolve_strict_replay_steps(
		FsqExecutableStepAdapter(default_evidence_policy=settings.harness.strict_core.evidence_policy()).to_executable_steps(case),
		settings,
	)
	harness = AndroidHarness(
		driver=UiAutomator2AndroidDriver(app_id=app_id, serial=settings.harness.android.serial),
		artifact_store=ArtifactStore(run_dir=run_dir),
		ai_assertion_evaluator=build_ai_assertion_evaluator(settings) if requires_ai_assertion else None,
	)
	artifact = _run_strict_core_steps(
		case_path=case_path,
		harness=harness,
		output_dir=run_dir,
		run_id=run_id,
		steps=steps,
		step_interval_seconds=settings.harness.strict_core.step_interval_seconds,
	)
	status, summary = _strict_report_status(artifact)
	state.add_event(
		request_id,
		RunEvent(
			run_id=run_id,
			task_id=case.id,
			type="run_completed",
			title="Strict YAML completed",
			message=summary,
			payload={"status": status, "report_path": str(artifact.path)},
		),
	)
	return TaskResult(
		task_id=case.id,
		status="success" if status == "passed" else "failed",
		steps=[],
		verification=VerificationResult(status="success" if status == "passed" else "failed", summary=summary),
		report=ReportArtifact(run_id=run_id, path=artifact.path, evidence_manifest_path=artifact.evidence_manifest_path),
	)


def _resolve_case_yaml_path(path_text: str, settings: Settings) -> Path:
	requested = Path(path_text.strip())
	candidates = [requested] if requested.is_absolute() else [settings.cases.dir / requested, Path.cwd() / requested]
	for candidate in candidates:
		if candidate.exists() and candidate.is_file():
			return candidate.resolve()
	raise FileNotFoundError(f"Case YAML not found: {path_text}")


def _run_strict_core_steps(
	*,
	case_path: Path,
	harness: AndroidHarness,
	output_dir: Path,
	run_id: str,
	steps: list[ExecutableStep],
	step_interval_seconds: float,
) -> ReportArtifact:
	normal_steps, teardown_steps = _split_trailing_teardown_steps(steps)
	recorder = EvidenceRecorder(run_id=run_id, output_dir=output_dir)
	StepSequenceRunner(
		harness=harness,
		evidence_recorder=recorder,
		step_interval_seconds=step_interval_seconds,
	).run_steps(run_id=run_id, steps=normal_steps, teardown_steps=teardown_steps)
	manifest_path = recorder.write_manifest()
	return CoreEvidenceReportGenerator().generate_from_manifest(manifest_path)


def _split_trailing_teardown_steps(steps: list[ExecutableStep]) -> tuple[list[ExecutableStep], list[ExecutableStep]]:
	split_at = len(steps)
	while split_at > 0 and steps[split_at - 1].kind == "teardown":
		split_at -= 1
	return steps[:split_at], steps[split_at:]


def _strict_report_status(artifact: ReportArtifact) -> tuple[str, str]:
	json_path = artifact.path.with_suffix(".json")
	try:
		payload = json.loads(json_path.read_text(encoding="utf-8"))
		status = str(payload.get("summary", {}).get("status") or "failed")
		failed_steps = payload.get("summary", {}).get("failed_steps")
		return status, f"Strict YAML {status}; failed_steps={failed_steps}"
	except Exception:
		return "failed", "Strict YAML run completed but report status could not be read."


def _case_requires_ai_assertion(case) -> bool:
	return any(step.action_name == "assertWithAI" for step in FsqExecutableStepAdapter().to_executable_steps(case))


def _resolve_strict_replay_steps(steps: list[ExecutableStep], settings: Settings) -> list[ExecutableStep]:
	allowed_names = set(settings.runtime_secrets.allowed_env_names)
	resolved_steps = []
	for step in steps:
		resolved_params = _resolve_replay_value(step.params, allowed_names, step.step_id)
		_validate_resolved_params(step, resolved_params)
		resolved_steps.append(step.model_copy(update={"params": resolved_params}))
	return resolved_steps


def _resolve_replay_value(value: Any, allowed_names: set[str], step_id: str) -> Any:
	ref = _as_runtime_secret_ref(value)
	if ref is not None:
		if ref.env_name not in allowed_names:
			raise ValueError(f"Runtime secret name is not allowed for strict replay: {ref.env_name}")
		secret_value = os.getenv(ref.env_name)
		if not secret_value:
			raise ValueError(f"Runtime secret is not set for strict replay: {ref.env_name}")
		return secret_value
	if isinstance(value, dict):
		return {key: _resolve_replay_value(item, allowed_names, step_id) for key, item in value.items()}
	if isinstance(value, list):
		return [_resolve_replay_value(item, allowed_names, step_id) for item in value]
	return value


def _as_runtime_secret_ref(value: Any) -> RuntimeSecretRef | None:
	if isinstance(value, RuntimeSecretRef):
		return value
	if isinstance(value, dict) and set(value) == {"runtimeSecret"}:
		try:
			return RuntimeSecretRef.model_validate(value)
		except ValidationError as exc:
			raise ValueError("Invalid runtimeSecret replay reference.") from exc
	return None


def _validate_resolved_params(step: ExecutableStep, params: dict[str, Any]) -> None:
	action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(step.action_name)
	if action_definition is None:
		return
	try:
		action_definition.params_model.model_validate(params)
	except ValidationError as exc:
		raise ValueError(f"Invalid strict replay command after runtime secret resolution: {step.step_id}") from exc


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
