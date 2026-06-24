from collections.abc import Awaitable, Callable
from typing import Any

from fsq_agent.models import CapabilityDefinition, CapabilityExecutionResult, CapabilityRegistrySnapshot, ConfigurationError, ExecutableStep


CommonCapabilityExecutor = Callable[[ExecutableStep], CapabilityExecutionResult | Awaitable[CapabilityExecutionResult]]
DriverCapabilityExecutor = Callable[[ExecutableStep, object], CapabilityExecutionResult]
HarnessCapabilityExecutor = Callable[[ExecutableStep, object], CapabilityExecutionResult]


class CapabilityRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, CapabilityDefinition] = {}
        self._aliases: dict[str, str] = {}

    @classmethod
    def from_definitions(cls, definitions: list[CapabilityDefinition]) -> "CapabilityRegistry":
        registry = cls()
        for definition in definitions:
            registry.register(definition)
        return registry

    def register(self, definition: CapabilityDefinition) -> None:
        if definition.name in self._definitions:
            raise ConfigurationError("Duplicate capability name.", context={"name": definition.name})
        if definition.name in self._aliases:
            raise ConfigurationError(
                "Capability name conflicts with an existing alias.",
                context={"name": definition.name, "existing_capability": self._aliases[definition.name]},
            )
        alias_map = dict(self._aliases)
        for alias in definition.aliases:
            if alias == definition.name:
                raise ConfigurationError("Capability alias duplicates its canonical name.", context={"name": definition.name})
            if alias in self._definitions:
                raise ConfigurationError(
                    "Capability alias conflicts with an existing capability name.",
                    context={"alias": alias, "name": definition.name},
                )
            existing = alias_map.get(alias)
            if existing is not None:
                raise ConfigurationError(
                    "Ambiguous capability alias.",
                    context={"alias": alias, "names": [existing, definition.name]},
                )
            alias_map[alias] = definition.name
        self._definitions[definition.name] = definition
        self._aliases = alias_map

    def resolve(self, name_or_alias: str) -> CapabilityDefinition | None:
        canonical_name = self._aliases.get(name_or_alias, name_or_alias)
        return self._definitions.get(canonical_name)

    def get(self, name: str) -> CapabilityDefinition | None:
        return self._definitions.get(name)

    def list_capabilities(self) -> list[CapabilityDefinition]:
        return list(self._definitions.values())

    def snapshot(self) -> CapabilityRegistrySnapshot:
        return CapabilityRegistrySnapshot(capabilities=self.list_capabilities())


class CapabilityExecutorBindings:
    def __init__(self) -> None:
        self._common: dict[str, CommonCapabilityExecutor] = {}
        self._driver: dict[str, DriverCapabilityExecutor] = {}
        self._harness: dict[str, HarnessCapabilityExecutor] = {}

    def bind_common(self, name: str, executor: CommonCapabilityExecutor) -> None:
        self._common[name] = executor

    def bind_driver(self, name: str, executor: DriverCapabilityExecutor) -> None:
        self._driver[name] = executor

    def bind_harness(self, name: str, executor: HarnessCapabilityExecutor) -> None:
        self._harness[name] = executor

    def common_executor(self, name: str) -> CommonCapabilityExecutor | None:
        return self._common.get(name)

    def driver_executor(self, name: str) -> DriverCapabilityExecutor | None:
        return self._driver.get(name)

    def harness_executor(self, name: str) -> HarnessCapabilityExecutor | None:
        return self._harness.get(name)