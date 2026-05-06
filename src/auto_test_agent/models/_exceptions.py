class AutoTestAgentError(Exception):
    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class ConfigurationError(AutoTestAgentError):
    pass


class PlanningError(AutoTestAgentError):
    pass


class ToolExecutionError(AutoTestAgentError):
    pass


class ObservationError(AutoTestAgentError):
    pass


class VerificationError(AutoTestAgentError):
    pass


class ReportGenerationError(AutoTestAgentError):
    pass