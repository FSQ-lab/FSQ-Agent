from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fsq_agent.core import CapabilityExecutorBindings, CapabilityRegistry, android_capability_definitions, web_capability_definitions, windows_capability_definitions
from fsq_agent.models import CapabilityDefinition, CapabilityExecutionResult, CommonToolCall, ConfigurationError, ExecutableStep, HarnessPlatform, ReplayPolicy
from fsq_agent.tools import CommonToolExecutor, CommonToolProvider, CommonToolRegistry, DefaultCommonToolProvider, FileOps


def common_capability_definitions() -> list[CapabilityDefinition]:
    return DefaultCommonToolProvider.capability_definitions()


def build_capability_registry(*, platform: HarnessPlatform = "android", include_ai_assertion: bool = True) -> CapabilityRegistry:
    return CapabilityRegistry.from_definitions(
        [
            *common_capability_definitions(),
            *_platform_capability_definitions(platform, include_ai_assertion=include_ai_assertion),
        ]
    )


def _platform_capability_definitions(platform: HarnessPlatform, *, include_ai_assertion: bool) -> list[CapabilityDefinition]:
    if platform == "android":
        return android_capability_definitions(include_ai_assertion=include_ai_assertion)
    if platform == "web":
        return web_capability_definitions(include_ai_assertion=include_ai_assertion)
    if platform == "windows":
        return windows_capability_definitions(include_ai_assertion=include_ai_assertion)
    raise ConfigurationError("Unsupported harness platform.", context={"platform": platform, "supported": ["android", "web", "windows"]})


def build_common_tool_provider(
    *,
    read_roots: list[Path] | None = None,
    write_root: Path | None = None,
    runtime_secret_settings: Any = None,
    local_tool_output_settings: Any = None,
    runs_dir: Path | None = None,
    run_id: str = "",
) -> DefaultCommonToolProvider:
    return DefaultCommonToolProvider(
        FileOps(read_roots=read_roots, write_root=write_root),
        runtime_secret_settings=runtime_secret_settings,
        local_tool_output_settings=local_tool_output_settings,
        runs_dir=runs_dir,
        run_id=run_id,
    )


def build_capability_executor_bindings(
    *,
    common_tool_providers: list[CommonToolProvider] | None = None,
) -> CapabilityExecutorBindings:
    registry = CommonToolRegistry.from_providers(common_tool_providers or [build_common_tool_provider()])
    executor = CommonToolExecutor(registry)
    bindings = CapabilityExecutorBindings()
    for definition in registry.list_capability_definitions():
        bindings.bind_common(definition.name, _common_executor(executor, definition.name))
    return bindings


def _common_executor(executor: CommonToolExecutor, tool_name: str):
    def execute(step: ExecutableStep) -> CapabilityExecutionResult:
        try:
            result = asyncio.run(executor.execute(CommonToolCall(tool_name=tool_name, arguments=step.params)))
        except RuntimeError as exc:
            if "asyncio.run() cannot be called from a running event loop" not in str(exc):
                raise
            raise ConfigurationError("Synchronous CommonTool execution requires a non-async caller.") from exc
        status = "passed" if result.status == "success" else "failed"
        metadata = dict(result.metadata)
        if result.artifact_path is not None:
            metadata["artifact_path"] = str(result.artifact_path)
        if result.artifact_content_chars is not None:
            metadata["artifact_content_chars"] = result.artifact_content_chars
        metadata["model_output"] = result.model_output
        return CapabilityExecutionResult(
            capability_name=tool_name,
            executor_kind="common",
            status=status,
            output=result.output,
            error_message=result.error,
            failure_category="configuration_error" if status == "failed" else None,
            duration_ms=result.duration_ms,
            replay=_replay_policy(result.metadata),
            sensitivity=result.sensitive,
            safe_replay_params=_safe_replay_params(result.metadata),
            metadata=metadata,
        )

    return execute


def _replay_policy(metadata: dict[str, object]) -> ReplayPolicy | None:
    replay = metadata.get("replay")
    if not isinstance(replay, dict):
        return None
    return ReplayPolicy.model_validate(replay)


def _safe_replay_params(metadata: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in metadata.items() if key in {"duration_ms", "reason"} and value is not None}