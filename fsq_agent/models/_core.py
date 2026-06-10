from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


StepPhase: TypeAlias = Literal["prepare", "invoke", "finalize"]
RunnerStatus: TypeAlias = Literal["pending", "running", "passed", "failed", "skipped", "cancelled"]
ExecutableStepKind: TypeAlias = Literal["action", "assertion", "observation", "diagnostic", "setup", "teardown"]
FailureCategory: TypeAlias = Literal[
    "configuration_error",
    "context_error",
    "target_resolution_error",
    "action_error",
    "assertion_error",
    "timeout_error",
    "observation_error",
    "artifact_error",
    "harness_error",
    "cancelled",
    "unknown",
]
RunnerEventType: TypeAlias = Literal[
    "session_start",
    "session_finish",
    "step_start",
    "phase_start",
    "harness_call_start",
    "harness_call_finish",
    "artifact_captured",
    "phase_finish",
    "step_error",
    "step_finish",
]
EvidenceArtifactKind: TypeAlias = Literal["screenshot", "ui_tree", "tool_call", "log", "json", "text", "other"]
HarnessPlatform: TypeAlias = Literal["android", "ios", "macos", "windows", "web"]


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: str | None = None
    step_index: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=1, ge=1)
    delay_ms: int = Field(default=0, ge=0)
    retry_on: list[FailureCategory] = Field(default_factory=list)


class EvidencePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capture_before: bool = False
    capture_after: bool = True
    capture_on_failure: bool = True
    artifact_kinds: list[EvidenceArtifactKind] = Field(default_factory=list)


class ExecutableStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    source_ref: SourceRef | None = None
    kind: ExecutableStepKind
    action_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    target_ref: str | None = None
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    evidence_policy: EvidencePolicy = Field(default_factory=EvidencePolicy)
    timeout_ms: int | None = Field(default=None, ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: EvidenceArtifactKind
    path: Path
    mime_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: HarnessPlatform
    session_id: str | None = None
    capabilities: dict[str, Any] = Field(default_factory=dict)
    current_url: str | None = None
    current_activity: str | None = None
    screen_size: tuple[int, int] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HarnessActionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RunnerStatus
    action_name: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    output: Any = None
    artifact_refs: list[HarnessArtifactRef] = Field(default_factory=list)
    error_message: str | None = None
    failure_category: FailureCategory | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepCallInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: StepPhase
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    status: RunnerStatus
    return_value: Any = None
    exception_type: str | None = None
    exception_message: str | None = None
    failure_category: FailureCategory | None = None


class EvidenceArtifactRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    kind: EvidenceArtifactKind
    path: Path
    mime_type: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    step_id: str | None = None
    phase: StepPhase | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StepPhaseReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    phase: StepPhase
    status: RunnerStatus
    duration_ms: int = Field(default=0, ge=0)
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    artifact_refs: list[EvidenceArtifactRef] = Field(default_factory=list)
    harness_call_refs: list[str] = Field(default_factory=list)


class RunnerStepResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    source_ref: SourceRef | None = None
    status: RunnerStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int = Field(default=0, ge=0)
    phase_reports: list[StepPhaseReport] = Field(default_factory=list)
    attempt_index: int = Field(default=1, ge=1)
    max_attempts: int = Field(default=1, ge=1)
    failure_category: FailureCategory | None = None
    error_message: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunnerEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str | None = None
    event_type: RunnerEventType
    run_id: str
    step_id: str | None = None
    phase: StepPhase | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle_id: str
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: str = "1.0"
    manifest_path: Path | None = None
    events: list[RunnerEvent] = Field(default_factory=list)
    steps: list[RunnerStepResult] = Field(default_factory=list)
    artifacts: list[EvidenceArtifactRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bundle: EvidenceBundle

