import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from fsq_agent.models import (
    CommonToolCall,
    CommonToolDefinition,
    CommonToolResult,
    LocalToolOutputSettings,
    RuntimeSecretSettings,
    ToolExecutionError,
)
from fsq_agent.tools._file_ops import FileOps
from fsq_agent.tools._tool_artifacts import ToolArtifactStore


class _ReadFileArgs(BaseModel):
    path: str = Field(description="Workspace-relative path to read.")


class _WriteFileArgs(BaseModel):
    path: str = Field(description="Workspace-relative path to write.")
    content: str = Field(description="Text content to write.")


class _WaitArgs(BaseModel):
    duration_ms: int = Field(ge=1, le=60000, description="Pure wait duration in milliseconds.")
    reason: str | None = Field(default=None, description="Optional short reason for the wait.")


class _RuntimeSecretArgs(BaseModel):
    name: str = Field(description="Allowed environment variable name to retrieve for the current run.")


class _SearchArtifactArgs(BaseModel):
    artifact_path: str = Field(description="Artifact path returned by a previous tool response.")
    query: str = Field(description="Text to search for inside the artifact.")
    case_sensitive: bool = Field(default=False, description="Whether the search is case-sensitive.")
    max_matches: int = Field(default=20, ge=1, le=100, description="Maximum number of matches to return.")
    context_chars: int = Field(default=300, ge=0, le=2000, description="Characters of context around each match.")


class _ReadArtifactSliceArgs(BaseModel):
    artifact_path: str = Field(description="Artifact path returned by a previous tool response.")
    offset: int = Field(default=0, ge=0, description="Character offset to start reading from.")
    length: int = Field(default=12000, ge=1, le=30000, description="Maximum characters to read.")


@runtime_checkable
class CommonToolProvider(Protocol):
    def list_capabilities(self) -> list[CommonToolDefinition]:
        ...

    async def invoke(self, call: CommonToolCall) -> CommonToolResult:
        ...


class CommonToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, CommonToolDefinition] = {}
        self._providers: dict[str, CommonToolProvider] = {}

    @classmethod
    def from_providers(cls, providers: list[CommonToolProvider]) -> "CommonToolRegistry":
        registry = cls()
        for provider in providers:
            registry.register_provider(provider)
        return registry

    def register_provider(self, provider: CommonToolProvider) -> None:
        for definition in provider.list_capabilities():
            if definition.name in self._definitions:
                raise ToolExecutionError("Duplicate CommonTool name.", context={"tool_name": definition.name})
            self._definitions[definition.name] = definition
            self._providers[definition.name] = provider

    def list_tools(self) -> list[CommonToolDefinition]:
        return list(self._definitions.values())

    def get(self, name: str) -> CommonToolDefinition | None:
        return self._definitions.get(name)

    def provider_for(self, name: str) -> CommonToolProvider | None:
        return self._providers.get(name)


class CommonToolExecutor:
    def __init__(self, registry: CommonToolRegistry) -> None:
        self.registry = registry

    async def execute(self, call: CommonToolCall) -> CommonToolResult:
        provider = self.registry.provider_for(call.tool_name)
        if provider is None:
            raise ToolExecutionError("Unknown CommonTool.", context={"tool_name": call.tool_name})
        return await provider.invoke(call)


class DefaultCommonToolProvider:
    def __init__(
        self,
        file_ops: FileOps,
        *,
        runtime_secret_settings: RuntimeSecretSettings | None = None,
        local_tool_output_settings: LocalToolOutputSettings | None = None,
        runs_dir: Path | None = None,
        run_id: str = "",
    ) -> None:
        self.file_ops = file_ops
        self.runtime_secret_settings = runtime_secret_settings or RuntimeSecretSettings()
        self.local_tool_output_settings = local_tool_output_settings or LocalToolOutputSettings()
        self.runs_dir = runs_dir
        self.run_id = run_id
        self.artifact_store = self._build_artifact_store()

    def configure_run(self, run_id: str) -> None:
        self.run_id = run_id
        self.artifact_store = self._build_artifact_store()

    def list_capabilities(self) -> list[CommonToolDefinition]:
        return [
            CommonToolDefinition(
                name="read_file",
                description="Read a scoped workspace file.",
                params_json_schema=_ReadFileArgs.model_json_schema(),
            ),
            CommonToolDefinition(
                name="write_file",
                description="Write a scoped output file.",
                params_json_schema=_WriteFileArgs.model_json_schema(),
            ),
            CommonToolDefinition(
                name="get_runtime_secret",
                description=(
                    "Retrieve one configured runtime secret from environment or .env-loaded values. "
                    "Never echo secret values in progress, evidence, or final output. "
                    f"Allowed names: {', '.join(self.runtime_secret_settings.allowed_env_names) or 'none'}."
                ),
                params_json_schema=_RuntimeSecretArgs.model_json_schema(),
            ),
            CommonToolDefinition(
                name="search_artifact",
                description="Search a large tool-output artifact by text and return offsets with local context.",
                params_json_schema=_SearchArtifactArgs.model_json_schema(),
            ),
            CommonToolDefinition(
                name="read_artifact_slice",
                description="Read a bounded character slice from a large tool-output artifact by offset and length.",
                params_json_schema=_ReadArtifactSliceArgs.model_json_schema(),
            ),
            CommonToolDefinition(
                name="wait_ms",
                description="Wait without touching or changing platform state.",
                params_json_schema=_WaitArgs.model_json_schema(),
            ),
        ]

    async def invoke(self, call: CommonToolCall) -> CommonToolResult:
        if call.tool_name == "read_file":
            return await self._read_file(call.arguments)
        if call.tool_name == "write_file":
            return await self._write_file(call.arguments)
        if call.tool_name == "get_runtime_secret":
            return await self._get_runtime_secret(call.arguments)
        if call.tool_name == "search_artifact":
            return await self._search_artifact(call.arguments)
        if call.tool_name == "read_artifact_slice":
            return await self._read_artifact_slice(call.arguments)
        if call.tool_name == "wait_ms":
            return await self._wait_ms(call.arguments)
        raise ToolExecutionError("Unknown CommonTool.", context={"tool_name": call.tool_name})

    async def _read_file(self, arguments: dict[str, Any]) -> CommonToolResult:
        parsed = _ReadFileArgs.model_validate(arguments)
        started = time.perf_counter()
        result = await self.file_ops.read_text({"path": parsed.path})
        return self._from_file_result("read_file", result, started, {"path": parsed.path})

    async def _write_file(self, arguments: dict[str, Any]) -> CommonToolResult:
        parsed = _WriteFileArgs.model_validate(arguments)
        started = time.perf_counter()
        result = await self.file_ops.write_text({"path": parsed.path, "content": parsed.content})
        return self._from_file_result("write_file", result, started, {"path": parsed.path})

    async def _get_runtime_secret(self, arguments: dict[str, Any]) -> CommonToolResult:
        parsed = _RuntimeSecretArgs.model_validate(arguments)
        started = time.perf_counter()
        allowed = set(self.runtime_secret_settings.allowed_env_names)
        if parsed.name not in allowed:
            raise ToolExecutionError("Runtime secret name is not allowed.", context={"name": parsed.name})
        value = os.getenv(parsed.name)
        if not value:
            raise ToolExecutionError("Runtime secret is not set.", context={"name": parsed.name})
        return CommonToolResult(
            tool_name="get_runtime_secret",
            status="success",
            output={"type": "runtime_secret", "name": parsed.name, "value": value, "sensitive": True},
            sensitive=True,
            duration_ms=int((time.perf_counter() - started) * 1000),
            metadata={"name": parsed.name},
        )

    async def _search_artifact(self, arguments: dict[str, Any]) -> CommonToolResult:
        parsed = _SearchArtifactArgs.model_validate(arguments)
        started = time.perf_counter()
        if not self.artifact_store:
            raise ToolExecutionError("Tool artifact storage is not enabled for this run.")
        result = self.artifact_store.search(
            parsed.artifact_path,
            parsed.query,
            parsed.case_sensitive,
            parsed.max_matches,
            parsed.context_chars,
        )
        return CommonToolResult(
            tool_name="search_artifact",
            status="success",
            output=result,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def _read_artifact_slice(self, arguments: dict[str, Any]) -> CommonToolResult:
        parsed = _ReadArtifactSliceArgs.model_validate(arguments)
        started = time.perf_counter()
        if not self.artifact_store:
            raise ToolExecutionError("Tool artifact storage is not enabled for this run.")
        result = self.artifact_store.read_slice(parsed.artifact_path, parsed.offset, parsed.length)
        return CommonToolResult(
            tool_name="read_artifact_slice",
            status="success",
            output=result,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )

    async def _wait_ms(self, arguments: dict[str, Any]) -> CommonToolResult:
        parsed = _WaitArgs.model_validate(arguments)
        started = time.perf_counter()
        await asyncio.sleep(parsed.duration_ms / 1000)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return CommonToolResult(
            tool_name="wait_ms",
            status="success",
            output={
                "type": "wait_completed",
                "duration_ms": parsed.duration_ms,
                "elapsed_ms": elapsed_ms,
                "reason": parsed.reason,
            },
            duration_ms=elapsed_ms,
        )

    def _from_file_result(self, tool_name: str, result: CommonToolResult, started: float, metadata: dict[str, Any]) -> CommonToolResult:
        payload = result.model_dump(mode="json")
        if result.status == "failed":
            return CommonToolResult(
                tool_name=tool_name,
                status="failed",
                output=payload,
                error=result.error,
                duration_ms=result.duration_ms,
                metadata=metadata,
            )
        return self._with_optional_artifact(
            tool_name,
            payload,
            started,
            metadata,
        )

    def _with_optional_artifact(
        self,
        tool_name: str,
        output: Any,
        started: float,
        metadata: dict[str, Any] | None = None,
    ) -> CommonToolResult:
        full_output = json.dumps(output, ensure_ascii=False, default=str)
        artifact_path = self.artifact_store.write(tool_name, full_output, metadata) if self.artifact_store else None
        return CommonToolResult(
            tool_name=tool_name,
            status="success",
            output=output,
            artifact_path=artifact_path,
            artifact_content_chars=len(full_output) if artifact_path else None,
            duration_ms=int((time.perf_counter() - started) * 1000),
            metadata=metadata or {},
        )

    def _build_artifact_store(self) -> ToolArtifactStore | None:
        if self.runs_dir and self.run_id and self.local_tool_output_settings.artifact_enabled:
            return ToolArtifactStore(self.runs_dir, self.run_id, self.local_tool_output_settings)
        return None