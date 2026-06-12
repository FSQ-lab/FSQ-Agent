import os
from typing import Any

from pydantic import ValidationError

from fsq_agent.config import Settings
from fsq_agent.models import ANDROID_ACTION_DEFINITIONS_BY_NAME, ConfigurationError, ExecutableStep, RuntimeSecretRef


def resolve_strict_replay_steps(steps: list[ExecutableStep], settings: Settings) -> list[ExecutableStep]:
    allowed_names = set(settings.runtime_secrets.allowed_env_names)
    resolved_steps: list[ExecutableStep] = []
    for step in steps:
        resolved_params = _resolve_value(step.params, allowed_names, step.step_id)
        _validate_resolved_params(step, resolved_params)
        resolved_steps.append(step.model_copy(update={"params": resolved_params}))
    return resolved_steps


def collect_runtime_secret_refs(value: Any) -> set[str]:
    names: set[str] = set()
    _collect_runtime_secret_refs(value, names)
    return names


def _resolve_value(value: Any, allowed_names: set[str], step_id: str) -> Any:
    ref = _as_runtime_secret_ref(value)
    if ref is not None:
        if ref.env_name not in allowed_names:
            raise ConfigurationError(
                "Runtime secret name is not allowed for strict replay.",
                context={"step_id": step_id, "name": ref.env_name},
            )
        secret_value = os.getenv(ref.env_name)
        if not secret_value:
            raise ConfigurationError(
                "Runtime secret is not set for strict replay.",
                context={"step_id": step_id, "name": ref.env_name},
            )
        return secret_value
    if isinstance(value, dict):
        return {key: _resolve_value(item, allowed_names, step_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, allowed_names, step_id) for item in value]
    return value


def _collect_runtime_secret_refs(value: Any, names: set[str]) -> None:
    ref = _as_runtime_secret_ref(value)
    if ref is not None:
        names.add(ref.env_name)
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_runtime_secret_refs(item, names)
        return
    if isinstance(value, list):
        for item in value:
            _collect_runtime_secret_refs(item, names)


def _as_runtime_secret_ref(value: Any) -> RuntimeSecretRef | None:
    if isinstance(value, RuntimeSecretRef):
        return value
    if isinstance(value, dict) and set(value) == {"runtimeSecret"}:
        try:
            return RuntimeSecretRef.model_validate(value)
        except ValidationError as exc:
            raise ConfigurationError(
                "Invalid runtimeSecret replay reference.",
                context={"validation_errors": _validation_errors(exc)},
            ) from exc
    return None


def _validate_resolved_params(step: ExecutableStep, params: dict[str, Any]) -> None:
    action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(step.action_name)
    if action_definition is None:
        return
    try:
        action_definition.params_model.model_validate(params)
    except ValidationError as exc:
        raise ConfigurationError(
            "Invalid strict replay command after runtime secret resolution.",
            context={
                "step_id": step.step_id,
                "action_name": step.action_name,
                "validation_errors": _validation_errors(exc),
            },
        ) from exc


def _validation_errors(error: ValidationError) -> list[dict[str, object]]:
    try:
        return error.errors(include_url=False, include_context=False)
    except TypeError:
        return error.errors()