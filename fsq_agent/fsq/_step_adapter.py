from typing import Any

from fsq_agent.models import ConfigurationError, ExecutableStep, FsqCase, SourceRef


_SETUP_ACTIONS = {"launchApp"}
_TEARDOWN_ACTIONS = {"killApp"}
_ASSERTION_ACTIONS = {"assert", "assertVisible", "assertNotVisible", "assertWithAI"}
_OBSERVATION_ACTIONS = {"takeScreenshot", "startRecording", "stopRecording"}


class FsqExecutableStepAdapter:
    def to_executable_steps(self, case: FsqCase) -> list[ExecutableStep]:
        return [self._to_step(case, command, index) for index, command in enumerate(case.commands)]

    def _to_step(self, case: FsqCase, command: Any, index: int) -> ExecutableStep:
        action_name, payload = self._parse_command(case, command, index)
        params = self._normalize_params(payload)
        timeout_ms = self._timeout_ms(params)
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

    def _timeout_ms(self, params: dict[str, Any]) -> int | None:
        timeout = params.get("timeout")
        return timeout if isinstance(timeout, int) and timeout >= 1 else None

    def _step_kind(self, action_name: str) -> str:
        if action_name in _SETUP_ACTIONS:
            return "setup"
        if action_name in _TEARDOWN_ACTIONS:
            return "teardown"
        if action_name in _ASSERTION_ACTIONS:
            return "assertion"
        if action_name in _OBSERVATION_ACTIONS:
            return "observation"
        return "action"
