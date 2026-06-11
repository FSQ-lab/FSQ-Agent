from typing import Protocol, runtime_checkable

from fsq_agent.models import (
    ExecutableStep,
    FailureCategory,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    HarnessFunctionSchema,
    StepPhase,
)


@runtime_checkable
class HarnessInterface(Protocol):
    def get_context(self) -> HarnessContext:
        ...

    def action_space(self) -> list[HarnessFunctionSchema]:
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

    def capture_artifact(
        self,
        kind: str,
        reason: str,
        context: HarnessContext,
        step_id: str,
        phase: StepPhase,
    ) -> HarnessArtifactRef:
        ...

    def classify_error(self, error: BaseException, phase: StepPhase, step: ExecutableStep) -> FailureCategory:
        ...
