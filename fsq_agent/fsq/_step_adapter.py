from typing import Any

from pydantic import ValidationError

from fsq_agent.models import (
    ANDROID_ACTION_DEFINITIONS_BY_NAME,
    ConfigurationError,
    ExecutableStep,
    FsqCase,
    SourceRef,
)


_OBSERVATION_ACTIONS = {"takeScreenshot", "startRecording", "stopRecording"}


class FsqExecutableStepAdapter:
    def to_executable_steps(self, case: FsqCase) -> list[ExecutableStep]:
        return [self._to_step(case, command, index) for index, command in enumerate(case.commands)]

    def _to_step(self, case: FsqCase, command: Any, index: int) -> ExecutableStep:
        action_name, payload = self._parse_command(case, command, index)
        raw_params = self._normalize_params(payload)
        timeout_ms = self._timeout_ms(raw_params)
        params = self._canonical_params(case, action_name, raw_params, index)
        return ExecutableStep(
            step_id=f"{case.id}-step-{index + 1:03d}",
            source_ref=SourceRef(
                source_type="fsq",
                source_id=str(case.path),
                step_index=index,
                metadata={"case_name": case.config.name, "platform": case.config.platform},
            ),
            kind=self._step_kind(action_name),
            action_name=action_name,
            params=params,
            timeout_ms=timeout_ms,
            metadata={
                "case_id": case.id,
                "case_name": case.config.name,
                "platform": case.config.platform,
                "raw_command": command,
            },
        )

    def _parse_command(self, case: FsqCase, command: Any, index: int) -> tuple[str, Any]:
        if isinstance(command, str):
            return command, None
        if isinstance(command, dict) and len(command) == 1:
            action_name, payload = next(iter(command.items()))
            return str(action_name), payload
        raise ConfigurationError(
            "Invalid FSQ command.",
            context={"path": str(case.path), "step_index": index},
        )

    def _normalize_params(self, payload: Any) -> dict[str, Any]:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return dict(payload)
        return {"value": payload}

    def _canonical_params(self, case: FsqCase, action_name: str, params: dict[str, Any], index: int) -> dict[str, Any]:
        action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(action_name)
        if action_definition is None:
            return params
        driver_params = {key: value for key, value in params.items() if key != "timeout"}
        try:
            parsed = action_definition.params_model.model_validate(driver_params)
        except ValidationError as exc:
            raise ConfigurationError(
                "Invalid FSQ command parameters.",
                context={
                    "path": str(case.path),
                    "step_index": index,
                    "action_name": action_name,
                    "validation_errors": self._validation_errors(exc),
                },
            ) from exc
        return parsed.model_dump(mode="json", exclude_none=True)

    def _timeout_ms(self, params: dict[str, Any]) -> int | None:
        timeout = params.get("timeout")
        return timeout if isinstance(timeout, int) and timeout >= 1 else None

    def _validation_errors(self, error: ValidationError) -> list[dict[str, object]]:
        try:
            return error.errors(include_url=False, include_context=False)
        except TypeError:
            return error.errors()

    def _step_kind(self, action_name: str) -> str:
        action_definition = ANDROID_ACTION_DEFINITIONS_BY_NAME.get(action_name)
        if action_definition is not None:
            return action_definition.step_kind
        if action_name in _OBSERVATION_ACTIONS:
            return "observation"
        return "action"
