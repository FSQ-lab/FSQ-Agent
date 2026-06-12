from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


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
AndroidSwipeDirection: TypeAlias = Literal["up", "down", "left", "right"]


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

    @field_serializer("path", when_used="json")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


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


class HarnessFunctionSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    params_json_schema: dict[str, Any] = Field(default_factory=dict)
    strict: bool = True
    platform: HarnessPlatform
    driver_method: str
    fsq_action_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AndroidLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resourceId: str | None = None
    accessibilityId: str | None = None
    text: str | None = None
    className: str | None = None
    xpath: str | None = None

    def has_value(self) -> bool:
        return any(isinstance(value, str) and value.strip() for value in self.model_dump().values())


class RuntimeSecretRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    env_name: str = Field(alias="runtimeSecret")

    @model_validator(mode="after")
    def _require_env_name(self) -> "RuntimeSecretRef":
        if self.env_name.strip():
            return self
        raise ValueError("requires non-empty runtimeSecret name")


class WaitMsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_ms: int = Field(ge=1, le=60000)
    reason: str | None = None


class AndroidPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int


class _AndroidTargetParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str | None = None
    locator: AndroidLocator | None = None

    @model_validator(mode="after")
    def _require_target(self) -> "_AndroidTargetParams":
        if self._has_target_value():
            return self
        raise ValueError("requires target or non-empty locator")

    def _has_target_value(self) -> bool:
        if isinstance(self.target, str) and self.target.strip():
            return True
        return self.locator is not None and self.locator.has_value()


class AndroidLaunchAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str | None = None


class AndroidKillAppParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str | None = None


class AndroidTapOnParams(_AndroidTargetParams):
    pass


class AndroidLongPressOnParams(_AndroidTargetParams):
    pass


class AndroidInputTextParams(_AndroidTargetParams):
    text: str


class AndroidPressKeyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str

    @model_validator(mode="after")
    def _require_key(self) -> "AndroidPressKeyParams":
        if self.key.strip():
            return self
        raise ValueError("requires non-empty key")


class AndroidSwipeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    direction: AndroidSwipeDirection | None = None
    start: AndroidPoint | None = None
    end: AndroidPoint | None = None
    duration: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _require_direction_or_points(self) -> "AndroidSwipeParams":
        has_direction = self.direction is not None
        has_points = self.start is not None and self.end is not None
        if has_direction or has_points:
            return self
        raise ValueError("requires direction or both start and end points")


class AndroidPerformActionsParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[dict[str, Any]]


class AndroidAssertVisibleParams(_AndroidTargetParams):
    optional: bool | None = None


class AndroidAssertNotVisibleParams(_AndroidTargetParams):
    optional: bool | None = None


class AndroidTextAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    equals: str | None = None

    @model_validator(mode="after")
    def _require_text_assertion(self) -> "AndroidTextAssertion":
        if isinstance(self.contains, str) or isinstance(self.equals, str):
            return self
        raise ValueError("requires contains or equals")


class AndroidElementState(AndroidLocator):
    enabled: bool | None = None
    checked: bool | None = None
    selected: bool | None = None
    clickable: bool | None = None
    focused: bool | None = None

    def has_state_assertion(self) -> bool:
        return any(
            value is not None
            for value in [self.enabled, self.checked, self.selected, self.clickable, self.focused]
        )


class AndroidAssertStateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    element: AndroidElementState | None = None
    text: AndroidTextAssertion | None = None
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_assertion(self) -> "AndroidAssertStateParams":
        if self.text is not None:
            return self
        if self.element is not None and (self.element.has_value() or self.element.has_state_assertion()):
            return self
        raise ValueError("requires text assertion or element locator/state assertion")


class AndroidAssertWithAIParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str
    optional: bool | None = None

    @model_validator(mode="after")
    def _require_prompt(self) -> "AndroidAssertWithAIParams":
        if self.prompt.strip():
            return self
        raise ValueError("requires non-empty prompt")


@dataclass(frozen=True)
class AndroidActionDefinition:
    fsq_action_name: str
    driver_method: str
    params_model: type[BaseModel]
    step_kind: ExecutableStepKind
    owner: Literal["driver", "harness"] = "driver"


ANDROID_ACTION_DEFINITIONS: tuple[AndroidActionDefinition, ...] = (
    AndroidActionDefinition("launchApp", "launch_app", AndroidLaunchAppParams, "setup"),
    AndroidActionDefinition("killApp", "kill_app", AndroidKillAppParams, "teardown"),
    AndroidActionDefinition("tapOn", "tap_on", AndroidTapOnParams, "action"),
    AndroidActionDefinition("assertVisible", "assert_visible", AndroidAssertVisibleParams, "assertion"),
    AndroidActionDefinition("performActions", "perform_actions", AndroidPerformActionsParams, "action"),
    AndroidActionDefinition("assert", "assert_state", AndroidAssertStateParams, "assertion"),
    AndroidActionDefinition("pressKey", "press_key", AndroidPressKeyParams, "action"),
    AndroidActionDefinition("inputText", "input_text", AndroidInputTextParams, "action"),
    AndroidActionDefinition("assertNotVisible", "assert_not_visible", AndroidAssertNotVisibleParams, "assertion"),
    AndroidActionDefinition("longPressOn", "long_press_on", AndroidLongPressOnParams, "action"),
    AndroidActionDefinition("swipe", "swipe", AndroidSwipeParams, "action"),
    AndroidActionDefinition("assertWithAI", "assert_with_ai", AndroidAssertWithAIParams, "assertion", "harness"),
)
ANDROID_ACTION_DEFINITIONS_BY_NAME: dict[str, AndroidActionDefinition] = {
    definition.fsq_action_name: definition for definition in ANDROID_ACTION_DEFINITIONS
}


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

    @field_serializer("path", when_used="json")
    def serialize_path(self, value: Path) -> str:
        return value.as_posix()


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
    metadata: dict[str, Any] = Field(default_factory=dict)


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

