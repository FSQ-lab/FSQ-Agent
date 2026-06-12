from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models._report import ReportArtifact


StepStatus = Literal["success", "failed", "skipped", "adjusted"]
VerificationStatus = Literal["success", "failed", "inconclusive"]
VerificationMode = Literal["strict", "normal", "goal"]
VerificationCriterionKind = Literal["goal", "assertion", "operation"]
PlanningReferenceKind = Literal["goal", "raw_case", "unknown"]


class VerificationCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    kind: VerificationCriterionKind
    required: bool = True
    source: str | None = None
    key_action_index: int | None = Field(default=None, ge=1)


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = "task"
    name: str = "Task"
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    planning_reference_kind: PlanningReferenceKind | None = None
    planning_reference_text: str | None = None
    key_actions: list[str] = Field(default_factory=list)
    verification_goal: str | None = None
    verification_criteria: list[VerificationCriterion] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300, ge=1)
    max_retries: int = Field(default=3, ge=0)
    knowledge_refs: list[str] = Field(default_factory=list)

    def required_verification_criteria(self) -> list[VerificationCriterion]:
        if self.verification_criteria:
            return [criterion for criterion in self.verification_criteria if criterion.required]
        if self.verification_goal:
            return [VerificationCriterion(text=self.verification_goal, kind="goal", source="verification_goal")]
        return [
            VerificationCriterion(text=criterion, kind="goal", source="acceptance_criteria")
            for criterion in self.acceptance_criteria
        ]

    def blocking_verification_criteria(self, mode: VerificationMode = "normal") -> list[VerificationCriterion]:
        criteria = self.required_verification_criteria()
        if mode == "strict":
            return criteria
        if mode == "goal":
            return [criterion for criterion in criteria if criterion.kind == "goal"]
        return [criterion for criterion in criteria if criterion.kind in {"goal", "assertion"}]


class ExecutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: int = Field(ge=1)
    action: str
    tool: str
    tool_input: dict[str, Any] = Field(default_factory=dict)
    expected_outcome: str
    timeout_seconds: int | None = Field(default=None, ge=1)
    max_attempts: int = Field(default=1, ge=1)


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    steps: list[ExecutionStep]
    rationale: str = ""
    warnings: list[str] = Field(default_factory=list)


class StepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: int = Field(ge=1)
    status: StepStatus
    actual_outcome: str
    screenshot_path: Path | None = None
    ui_tree_snapshot: dict[str, Any] | None = None
    duration_ms: int = Field(default=0, ge=0)
    error: str | None = None
    tool_name: str | None = None
    tool_output: Any = None


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VerificationStatus
    summary: str
    satisfied_criteria: list[str] = Field(default_factory=list)
    unmet_criteria: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: VerificationStatus
    steps: list[StepResult]
    verification: VerificationResult
    report: ReportArtifact
    duration_ms: int = Field(default=0, ge=0)