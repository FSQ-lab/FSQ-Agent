from auto_test_agent.models import CLIToolConfig, ToolDefinition


class CapabilityRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    @classmethod
    def from_cli_tools(cls, cli_tools: list[CLIToolConfig]) -> "CapabilityRegistry":
        registry = cls()
        for cli_tool in cli_tools:
            registry.register(
                ToolDefinition(
                    name=cli_tool.name,
                    kind="cli",
                    description=cli_tool.description,
                    command=cli_tool.command,
                )
            )
        registry.register(ToolDefinition(name="file.read", kind="file", description="Read a text file."))
        registry.register(ToolDefinition(name="file.write", kind="file", description="Write a text file."))
        return registry

    def register(self, definition: ToolDefinition) -> None:
        self._definitions[definition.name] = definition

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def get(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)