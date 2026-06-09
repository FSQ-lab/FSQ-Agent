from typing import Any, Protocol, runtime_checkable

from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    StepPhase,
)


@runtime_checkable
class HarnessInterface(Protocol):
    def get_context(self) -> HarnessContext:
        ...

    def action_space(self) -> dict[str, Any]:
        ...

    def before_action(self, step: ExecutableStep, context: HarnessContext) -> None:
        ...

    def invoke_action(self, step: ExecutableStep, context: HarnessContext) -> HarnessActionResult:
        ...

    def after_action(
        self,
        step: ExecutableStep,
        context: HarnessContext,
        action_result: HarnessActionResult,
    ) -> None:
        ...

    def capture_artifact(self, kind: str, reason: str, context: HarnessContext) -> HarnessArtifactRef:
        ...

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        ...

