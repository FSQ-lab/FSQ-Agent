from abc import ABC, abstractmethod
from typing import Any

from fsq_agent.models import PlatformActionDefinition, PlatformActionResult


class PlatformAdapter(ABC):
    @abstractmethod
    def action_space(self) -> list[PlatformActionDefinition]:
        raise NotImplementedError

    @abstractmethod
    async def invoke_action(
        self,
        action_name: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> PlatformActionResult:
        raise NotImplementedError

    def action_definition(self, action_name: str) -> PlatformActionDefinition | None:
        for definition in self.action_space():
            if definition.name == action_name:
                return definition
        return None
