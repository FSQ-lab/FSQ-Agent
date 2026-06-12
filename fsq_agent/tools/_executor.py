from fsq_agent.models import ToolCall, ToolExecutionError, ToolResult
from fsq_agent.tools._cli_runner import CLIRunner
from fsq_agent.tools._file_ops import FileOps
from fsq_agent.tools._registry import CapabilityRegistry


class ToolExecutor:
    def __init__(
        self,
        registry: CapabilityRegistry,
        cli_runner: CLIRunner,
        file_ops: FileOps,
    ) -> None:
        self.registry = registry
        self.cli_runner = cli_runner
        self.file_ops = file_ops

    async def execute(self, call: ToolCall) -> ToolResult:
        definition = self.registry.get(call.tool_name)
        kind = call.kind or (definition.kind if definition else None)
        if kind is None:
            raise ToolExecutionError("Unknown tool.", context={"tool": call.tool_name})

        if kind == "cli":
            return await self.cli_runner.run(
                call.tool_name,
                call.arguments,
                timeout_seconds=call.timeout_seconds,
            )
        if kind == "file":
            if call.tool_name == "file.read":
                return await self.file_ops.read_text(call.arguments)
            if call.tool_name == "file.write":
                return await self.file_ops.write_text(call.arguments)
            raise ToolExecutionError("Unknown file operation.", context={"tool": call.tool_name})
        raise ToolExecutionError("Unsupported tool kind.", context={"tool": call.tool_name, "kind": kind})