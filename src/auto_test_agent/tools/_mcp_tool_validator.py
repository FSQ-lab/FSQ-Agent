from copy import deepcopy
from typing import Any

from auto_test_agent.models import (
    MCPToolValidationIssue,
    MCPToolValidationSettings,
    ToolExecutionError,
)


class MCPToolValidator:
    def __init__(self, settings: MCPToolValidationSettings) -> None:
        self.settings = settings

    def validate_tools(self, server_name: str, tools: list[Any]) -> list[MCPToolValidationIssue]:
        if not self.settings.enabled:
            return []
        issues: list[MCPToolValidationIssue] = []
        for tool in tools:
            issue = self._validate_tool(server_name, tool)
            if issue:
                if self.settings.invalid_tool_policy == "fail_fast":
                    raise ToolExecutionError(
                        "MCP tool failed compatibility validation.",
                        context=issue.model_dump(mode="json"),
                    )
                issues.append(issue)
        return issues

    def _validate_tool(self, server_name: str, tool: Any) -> MCPToolValidationIssue | None:
        tool_name = str(getattr(tool, "name", ""))
        schema = getattr(tool, "inputSchema", None)
        if not isinstance(schema, dict):
            return self._issue(server_name, tool_name, "MCP tool inputSchema must be an object.")

        schema_copy = deepcopy(schema)
        schema_copy.setdefault("properties", {})
        unsupported = self._find_unsupported_schema_keyword(schema_copy)
        if unsupported:
            keyword, path = unsupported
            return self._issue(
                server_name,
                tool_name,
                f"Unsupported JSON Schema keyword: {keyword}",
                path,
            )

        if self.settings.strict_schema:
            try:
                from agents.strict_schema import ensure_strict_json_schema
            except ImportError as exc:
                raise ToolExecutionError("openai-agents is required for MCP schema validation.") from exc
            try:
                ensure_strict_json_schema(schema_copy)
            except Exception as exc:  # pragma: no cover - exact SDK exceptions are version-dependent.
                return self._issue(server_name, tool_name, f"Unable to convert schema to strict mode: {exc}")
        return None

    def _find_unsupported_schema_keyword(self, value: Any, path: str = "$") -> tuple[str, str] | None:
        if isinstance(value, dict):
            for key, item in value.items():
                current_path = f"{path}.{key}"
                if key in self.settings.unsupported_schema_keywords:
                    return key, current_path
                nested = self._find_unsupported_schema_keyword(item, current_path)
                if nested:
                    return nested
        elif isinstance(value, list):
            for index, item in enumerate(value):
                nested = self._find_unsupported_schema_keyword(item, f"{path}[{index}]")
                if nested:
                    return nested
        return None

    def _issue(
        self,
        server_name: str,
        tool_name: str,
        reason: str,
        schema_path: str = "",
    ) -> MCPToolValidationIssue:
        return MCPToolValidationIssue(
            server_name=server_name,
            tool_name=tool_name,
            reason=reason,
            policy=self.settings.invalid_tool_policy,
            schema_path=schema_path,
        )
