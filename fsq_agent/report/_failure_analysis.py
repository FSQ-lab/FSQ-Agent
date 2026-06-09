from typing import Any

from fsq_agent.models import StepResult, VerificationResult


_TOOL_USAGE_MARKERS = (
    "invalid argument",
    "invalid parameter",
    "schema",
    "unsupported",
    "not supported",
    "only supported",
    "parameter is",
    "failed to perform actions",
    "tool usage issue",
    "conflicting key identities",
    "ambiguous",
)

_SEMANTIC_ACTION_MARKERS = (
    "presskey",
    "press key",
    "key action",
    "ordered key",
)


class FailureAnalyzer:
    def classify(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]] | None = None,
        platform_actions: list[dict[str, Any]] | None = None,
    ) -> str:
        if verification.status == "success":
            return "success"
        labels: list[str] = []
        if self._has_platform_action_error(platform_actions or []):
            labels.append("platform_action_issue")
        if self._has_tool_usage_error(steps, verification, tool_calls or []):
            labels.append("tool_usage_error")
        if self._has_semantic_action_unmet(verification):
            labels.append("semantic_action_unmet")
        if labels:
            return " + ".join(labels)
        if any(step.status == "failed" and step.error for step in steps):
            return "execution issue"
        if verification.status == "inconclusive":
            return "verification issue"
        return "planning issue"

    def _has_tool_usage_error(
        self,
        steps: list[StepResult],
        verification: VerificationResult,
        tool_calls: list[dict[str, Any]],
    ) -> bool:
        texts = [self._normalize(step.error) for step in steps if step.status == "failed" and step.error]
        texts.extend(self._normalize(value) for value in verification.diagnostics)
        for call in tool_calls:
            texts.append(self._normalize(call.get("output_preview")))
            texts.append(self._normalize(call.get("error")))
        return any(any(marker in text for marker in _TOOL_USAGE_MARKERS) for text in texts)

    def _has_platform_action_error(self, platform_actions: list[dict[str, Any]]) -> bool:
        return any(action.get("status") == "failed" for action in platform_actions)

    def _has_semantic_action_unmet(self, verification: VerificationResult) -> bool:
        texts = [self._normalize(value) for value in verification.unmet_criteria]
        texts.extend(self._normalize(value) for value in verification.diagnostics)
        texts.append(self._normalize(verification.summary))
        return any(any(marker in text for marker in _SEMANTIC_ACTION_MARKERS) for text in texts)

    def _normalize(self, value: Any) -> str:
        return str(value or "").lower()
