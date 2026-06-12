import inspect
import json
import time
from typing import Any

from fsq_agent.models import CommonToolCall, CommonToolResult, LocalToolOutputSettings, RunEvent, RunEventSink
from fsq_agent.tools._common import CommonToolExecutor, CommonToolRegistry, DefaultCommonToolProvider


class AgentsCommonToolAdapter:
    def __init__(
        self,
        registry: CommonToolRegistry,
        *,
        local_tool_output_settings: LocalToolOutputSettings | None = None,
    ) -> None:
        self.registry = registry
        self.executor = CommonToolExecutor(registry)
        self.local_tool_output_settings = local_tool_output_settings or LocalToolOutputSettings()
        self.run_id = ""
        self.task_id = ""
        self.event_sink: RunEventSink | None = None

    def build_tools(
        self,
        function_tool_cls: Any,
        *,
        run_id: str = "",
        task_id: str = "",
        event_sink: RunEventSink | None = None,
    ) -> list[Any]:
        self.run_id = run_id
        self.task_id = task_id
        self.event_sink = event_sink
        self._configure_provider_runs(run_id)
        return [
            function_tool_cls(
                name=definition.name,
                description=definition.description,
                params_json_schema=definition.params_json_schema,
                on_invoke_tool=self._handler_for(definition.name),
            )
            for definition in self.registry.list_tools()
        ]

    def _handler_for(self, tool_name: str):
        async def invoke(_ctx: Any, args: str) -> str:
            started = time.perf_counter()
            try:
                arguments = self._parse_args(args)
                await self._emit_tool_started(tool_name, arguments)
                result = await self.executor.execute(CommonToolCall(tool_name=tool_name, arguments=arguments))
            except Exception as exc:
                result = CommonToolResult(
                    tool_name=tool_name,
                    status="failed",
                    error=str(exc) or exc.__class__.__name__,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                output = self._format_tool_response(result)
                await self._emit_tool_failed(tool_name, result.error or "CommonTool failed.", started)
                return output
            output = self._format_tool_response(result)
            if result.status == "failed":
                await self._emit_tool_failed(tool_name, result.error or "CommonTool failed.", started)
            else:
                await self._emit_tool_completed(tool_name, output, started, result)
            return output

        return invoke

    def _parse_args(self, args: str) -> dict[str, Any]:
        if not args:
            return {}
        payload = json.loads(args)
        if not isinstance(payload, dict):
            raise ValueError("CommonTool arguments must be a JSON object.")
        return payload

    def _format_tool_response(self, result: CommonToolResult) -> str:
        payload = result.model_dump(mode="json")
        if result.sensitive:
            return json.dumps(
                {
                    "tool_name": result.tool_name,
                    "model_output": "full",
                    "sensitive": True,
                    "artifact": self._artifact_payload(result),
                    "result": payload,
                },
                ensure_ascii=False,
                default=str,
            )
        full_output = json.dumps(payload, ensure_ascii=False, default=str)
        settings = self.local_tool_output_settings
        if len(full_output) <= settings.full_output_max_chars:
            return json.dumps(
                {
                    "tool_name": result.tool_name,
                    "model_output": "full",
                    "artifact": self._artifact_payload(result),
                    "result": payload,
                },
                ensure_ascii=False,
                default=str,
            )

        preview = full_output[: settings.historical_preview_chars]
        response = {
            "tool_name": result.tool_name,
            "model_output": settings.historical_output_mode,
            "artifact": self._artifact_payload(result),
            "preview": preview,
            "instructions": "Use search_artifact or read_artifact_slice with artifact.path when details beyond the preview are needed.",
        }
        encoded = json.dumps(response, ensure_ascii=False, default=str)
        if len(encoded) <= settings.model_response_max_chars:
            return encoded
        preview_limit = len(preview)
        while preview_limit > 0:
            response["preview"] = preview[:preview_limit]
            encoded = json.dumps(response, ensure_ascii=False, default=str)
            if len(encoded) <= settings.model_response_max_chars:
                return encoded
            preview_limit //= 2
        response["preview"] = ""
        return json.dumps(response, ensure_ascii=False, default=str)

    def _artifact_payload(self, result: CommonToolResult) -> dict[str, Any]:
        return {
            "path": str(result.artifact_path) if result.artifact_path else None,
            "content_chars": result.artifact_content_chars,
        }

    def _redact_sensitive_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        output = payload.get("output")
        if isinstance(output, dict) and "value" in output:
            redacted_output = dict(output)
            redacted_output["value"] = "***"
            payload = dict(payload)
            payload["output"] = redacted_output
        return payload

    def _redact_sensitive_response(self, output: str) -> str:
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            return output
        if not isinstance(payload, dict):
            return output
        result = payload.get("result")
        if isinstance(result, dict):
            payload = dict(payload)
            payload["result"] = self._redact_sensitive_result(dict(result))
            return json.dumps(payload, ensure_ascii=False, default=str)
        return json.dumps(self._redact_sensitive_result(payload), ensure_ascii=False, default=str)

    async def _emit_tool_started(self, tool_name: str, arguments: dict[str, Any] | str) -> None:
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_started",
                title="Tool call started",
                message=f"Calling {tool_name}.",
                tool_name=tool_name,
                tool_arguments=self._redact(arguments),
                payload={"tool_origin": "common"},
            )
        )

    async def _emit_tool_completed(self, tool_name: str, output: str, started: float, result: CommonToolResult) -> None:
        preview_output = self._redact_sensitive_response(output) if result.sensitive else output
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_completed",
                title="Tool call completed",
                message=f"{tool_name} completed.",
                tool_name=tool_name,
                tool_output_preview=self._preview(preview_output),
                duration_ms=result.duration_ms or int((time.perf_counter() - started) * 1000),
                payload={"tool_origin": "common", "artifact_path": str(result.artifact_path) if result.artifact_path else None},
            )
        )

    async def _emit_tool_failed(self, tool_name: str, error: str, started: float) -> None:
        await self._emit(
            RunEvent(
                run_id=self.run_id,
                task_id=self.task_id,
                type="tool_call_failed",
                title="Tool call failed",
                message=error,
                tool_name=tool_name,
                duration_ms=int((time.perf_counter() - started) * 1000),
                payload={"tool_origin": "common"},
            )
        )

    async def _emit(self, event: RunEvent) -> None:
        if not self.event_sink or not self.run_id or not self.task_id:
            return
        result = self.event_sink(event)
        if inspect.isawaitable(result):
            await result

    def _preview(self, value: Any, limit: int = 1000) -> str:
        text = value if isinstance(value, str) else repr(value)
        text = text.replace("\r", " ").replace("\n", " ")
        return text if len(text) <= limit else f"{text[:limit]}..."

    def _redact(self, value: Any) -> Any:
        sensitive = ("token", "key", "secret", "password", "authorization", "cookie")
        if isinstance(value, dict):
            return {key: "***" if any(part in str(key).lower() for part in sensitive) else self._redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value

    def _configure_provider_runs(self, run_id: str) -> None:
        for provider in self.registry._providers.values():
            if isinstance(provider, DefaultCommonToolProvider):
                provider.configure_run(run_id)