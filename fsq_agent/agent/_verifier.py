import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fsq_agent.models import AgentFinalOutput, StepResult, Task, VerificationResult

from fsq_agent.agent._structured_output import coerce_agent_final_output


class Verifier:
    async def verify(self, task: Task, results: list[StepResult], events_path: Path | None = None) -> VerificationResult:
        event_result = self._verify_from_events(task, events_path)
        if event_result is not None and event_result.status != "inconclusive":
            return event_result

        sdk_steps = [step for step in results if step.tool_name == "openai_agents.runner"]
        if sdk_steps:
            sdk_result = self._verify_sdk_result(task, sdk_steps[-1])
            if event_result is not None and sdk_result.status == "inconclusive":
                return event_result
            failed_steps = [step for step in results if step.status == "failed" and step.tool_name != "openai_agents.runner"]
            if failed_steps and sdk_result.status == "success":
                return VerificationResult(
                    status="inconclusive",
                    summary=f"{sdk_result.summary} Success was downgraded because one or more execution steps failed.",
                    satisfied_criteria=sdk_result.satisfied_criteria,
                    unmet_criteria=sdk_result.unmet_criteria,
                    diagnostics=[*sdk_result.diagnostics, *[step.error or step.actual_outcome for step in failed_steps]],
                )
            return sdk_result

        failed_steps = [step for step in results if step.status == "failed"]
        if failed_steps:
            return VerificationResult(
                status="failed",
                summary="One or more execution steps failed.",
                unmet_criteria=task.acceptance_criteria or ["The task flow did not complete successfully."],
                diagnostics=[step.error or step.actual_outcome for step in failed_steps],
            )
        return VerificationResult(
            status="inconclusive",
            summary="Execution completed, but final acceptance criteria require an MCP/LLM verifier or domain-specific checks.",
            satisfied_criteria=[],
            unmet_criteria=task.acceptance_criteria or ["No derived acceptance criteria were reported."],
            diagnostics=["Verifier avoids claiming UI task success without direct evidence."],
        )

    def _verify_sdk_result(self, task: Task, step: StepResult) -> VerificationResult:
        payload = self._parse_final_output(step.actual_outcome)
        if payload is None:
            return VerificationResult(
                status="inconclusive",
                summary="OpenAI Agents SDK completed, but the final output was not valid verification JSON.",
                satisfied_criteria=[],
                unmet_criteria=task.acceptance_criteria or ["No derived acceptance criteria were reported."],
                diagnostics=[step.actual_outcome],
            )

        status = payload.status
        satisfied_criteria = list(payload.satisfied_criteria)
        unmet_criteria = list(payload.unmet_criteria)
        evidence = list(payload.evidence)
        errors = list(payload.errors)
        plan_updates = list(payload.plan_updates)
        summary = payload.summary or "Task verification completed."
        expected_criteria = self._expected_criteria(task, satisfied_criteria, unmet_criteria)

        if status == "success" and not expected_criteria:
            status = "inconclusive"
            unmet_criteria = ["No acceptance criteria were provided by the user or derived by the agent."]
            summary = f"{summary} Success was downgraded because no acceptance criteria were reported."

        if status == "success" and unmet_criteria:
            status = "inconclusive"
            summary = f"{summary} Success was downgraded because unmet criteria were reported."
        if status == "success" and len(satisfied_criteria) < len(expected_criteria):
            status = "inconclusive"
            missing = [criterion for criterion in expected_criteria if criterion not in satisfied_criteria]
            unmet_criteria = [*unmet_criteria, *missing]
            summary = f"{summary} Success was downgraded because not all task criteria were explicitly satisfied."
        if status in {"failed", "inconclusive"} and not unmet_criteria:
            unmet_criteria = [criterion for criterion in expected_criteria if criterion not in satisfied_criteria]

        diagnostics = [*evidence, *plan_updates, *errors]
        if not diagnostics:
            diagnostics = [step.actual_outcome]
        return VerificationResult(
            status=status,
            summary=summary,
            satisfied_criteria=satisfied_criteria,
            unmet_criteria=unmet_criteria,
            diagnostics=diagnostics,
        )

    def _parse_final_output(self, output: object) -> AgentFinalOutput | None:
        return coerce_agent_final_output(output)

    def _expected_criteria(
        self,
        task: Task,
        satisfied_criteria: list[str],
        unmet_criteria: list[str],
    ) -> list[str]:
        if task.acceptance_criteria:
            return task.acceptance_criteria
        seen: set[str] = set()
        criteria: list[str] = []
        for criterion in [*satisfied_criteria, *unmet_criteria]:
            if criterion and criterion not in seen:
                seen.add(criterion)
                criteria.append(criterion)
        return criteria

    def _verify_from_events(self, task: Task, events_path: Path | None) -> VerificationResult | None:
        if not task.acceptance_criteria or not events_path or not events_path.exists():
            return None
        calls = self._load_tool_calls(events_path)
        if not calls:
            return None

        evidence = _EventEvidence.from_calls(calls)
        satisfied: list[str] = []
        unmet: list[str] = []
        diagnostics: list[str] = []
        for criterion in task.acceptance_criteria:
            proof = evidence.satisfies(criterion)
            if proof:
                satisfied.append(criterion)
                diagnostics.append(proof)
            else:
                unmet.append(criterion)

        diagnostics.extend(evidence.tool_diagnostics())
        if satisfied and not unmet:
            return VerificationResult(
                status="success",
                summary="Task success was verified after execution from recorded tool-call evidence.",
                satisfied_criteria=satisfied,
                unmet_criteria=[],
                diagnostics=diagnostics,
            )
        if satisfied:
            return VerificationResult(
                status="failed",
                summary="Task execution completed, but independent verification found unmet acceptance criteria.",
                satisfied_criteria=satisfied,
                unmet_criteria=unmet,
                diagnostics=diagnostics,
            )
        return VerificationResult(
            status="inconclusive",
            summary="Execution completed, but recorded tool-call evidence was not enough to verify task success independently.",
            satisfied_criteria=[],
            unmet_criteria=task.acceptance_criteria,
            diagnostics=diagnostics or ["No acceptance criteria could be matched to recorded tool-call evidence."],
        )

    def _load_tool_calls(self, events_path: Path) -> list["_RecordedToolCall"]:
        starts: dict[str, dict[str, Any]] = {}
        calls: list[_RecordedToolCall] = []
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            call_id = str(event.get("tool_call_id") or "")
            if event_type == "tool_call_started" and call_id:
                starts[call_id] = event
                continue
            if event_type not in {"tool_call_completed", "tool_call_failed"} or not call_id:
                continue
            start = starts.get(call_id, {})
            calls.append(
                _RecordedToolCall(
                    tool_name=str(start.get("tool_name") or event.get("tool_name") or "unknown"),
                    status="failed" if event_type == "tool_call_failed" else "completed",
                    arguments=self._coerce_arguments(start.get("tool_arguments")),
                    output=str(event.get("tool_output_preview") or event.get("message") or ""),
                    message=str(event.get("message") or ""),
                )
            )
        return calls

    def _coerce_arguments(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}


@dataclass(frozen=True)
class _RecordedToolCall:
    tool_name: str
    status: str
    arguments: dict[str, Any]
    output: str
    message: str = ""


class _EventEvidence:
    def __init__(self, calls: list[_RecordedToolCall]) -> None:
        self.calls = calls
        self.selector_to_elements: dict[str, set[str]] = {}
        self.element_to_selector: dict[str, str] = {}
        self._index_elements()

    @classmethod
    def from_calls(cls, calls: list[_RecordedToolCall]) -> "_EventEvidence":
        return cls(calls)

    def satisfies(self, criterion: str) -> str | None:
        if "pressKey: Enter" in criterion:
            return self._press_key_enter_proof()
        if "inputText" in criterion:
            selector = self._resource_id(criterion)
            text = self._input_text(criterion)
            return self._input_text_proof(selector, text)
        if criterion.startswith("Key action") and "tapOn" in criterion:
            return self._tap_proof(self._resource_id(criterion))
        if "assertVisible" in criterion:
            return self._find_proof(self._locator_selector(criterion))
        if "assert" in criterion and "contains" in criterion:
            selector = self._resource_id(criterion)
            expected_text = self._contains_text(criterion)
            return self._text_proof(selector, expected_text)
        return None

    def tool_diagnostics(self) -> list[str]:
        diagnostics: list[str] = []
        for call in self.calls:
            if call.tool_name == "appium_mobile_press_key" and self._has_conflicting_key_identity(call.arguments):
                diagnostics.append(
                    "Tool usage issue: appium_mobile_press_key was called with conflicting key identities. "
                    f"Arguments were {json.dumps(call.arguments, ensure_ascii=False)}."
                )
            if call.status == "failed" and not self._is_nonfatal_cleanup_failure(call):
                diagnostics.append(f"Tool failure: {call.tool_name}: {call.output or call.message}")
        return diagnostics

    def _index_elements(self) -> None:
        for call in self.calls:
            if call.status != "completed" or call.tool_name != "appium_find_element":
                continue
            if "Successfully found element" not in call.output:
                continue
            selector = str(call.arguments.get("selector") or "")
            element_id = self._element_id(call.output)
            if not selector or not element_id:
                continue
            self.selector_to_elements.setdefault(selector, set()).add(element_id)
            self.element_to_selector[element_id] = selector

    def _find_proof(self, selector: str | None) -> str | None:
        if not selector:
            return None
        for call in self.calls:
            if call.tool_name == "appium_find_element" and call.status == "completed" and call.arguments.get("selector") == selector and "Successfully found element" in call.output:
                return f"Verified visible element with selector {selector}."
        return None

    def _tap_proof(self, selector: str | None) -> str | None:
        if not selector:
            return None
        element_ids = self.selector_to_elements.get(selector, set())
        for call in self.calls:
            if call.tool_name == "appium_gesture" and call.status == "completed" and call.arguments.get("action") == "tap" and call.arguments.get("elementUUID") in element_ids and "Successfully tapped element" in call.output:
                return f"Verified tap on element located by {selector}."
        return None

    def _input_text_proof(self, selector: str | None, text: str | None) -> str | None:
        if not selector or text is None:
            return None
        element_ids = self.selector_to_elements.get(selector, set())
        for call in self.calls:
            if call.tool_name == "appium_set_value" and call.status == "completed" and call.arguments.get("elementUUID") in element_ids and call.arguments.get("text") == text and "Successfully set value" in call.output:
                return f"Verified text input into element located by {selector}."
        return None

    def _press_key_enter_proof(self) -> str | None:
        for call in self.calls:
            if call.tool_name != "appium_mobile_press_key" or call.status != "completed":
                continue
            if self._has_conflicting_key_identity(call.arguments):
                continue
            key = str(call.arguments.get("key") or "").upper()
            key_code = call.arguments.get("keyCode")
            if key == "ENTER" or key_code == 66:
                return "Verified Enter key through appium_mobile_press_key."
        return None

    def _text_proof(self, selector: str | None, expected_text: str | None) -> str | None:
        if not selector or expected_text is None:
            return None
        element_ids = self.selector_to_elements.get(selector, set())
        for call in self.calls:
            if call.tool_name == "appium_get_text" and call.status == "completed" and call.arguments.get("elementUUID") in element_ids and f"Successfully got text {expected_text}" in call.output:
                return f"Verified text {expected_text} from element located by {selector}."
        return None

    def _has_conflicting_key_identity(self, arguments: dict[str, Any]) -> bool:
        key = str(arguments.get("key") or "").upper()
        key_code = arguments.get("keyCode")
        expected_codes = {"BACK": 4, "ENTER": 66}
        return bool(key and key_code is not None and expected_codes.get(key) != key_code)

    def _is_nonfatal_cleanup_failure(self, call: _RecordedToolCall) -> bool:
        return call.tool_name == "appium_alert" and "No alert is present" in (call.output or call.message)

    def _locator_selector(self, criterion: str) -> str | None:
        accessibility_match = re.search(r"accessibilityId=([^)]*)", criterion)
        if accessibility_match:
            return accessibility_match.group(1)
        return self._resource_id(criterion)

    def _resource_id(self, criterion: str) -> str | None:
        match = re.search(r"resourceId=([^);]+)", criterion)
        return match.group(1) if match else None

    def _input_text(self, criterion: str) -> str | None:
        match = re.search(r"inputText\s+(.+?)\s+into", criterion)
        return match.group(1) if match else None

    def _contains_text(self, criterion: str) -> str | None:
        match = re.search(r'"contains":\s*"([^"]+)"', criterion)
        return match.group(1) if match else None

    def _element_id(self, output: str) -> str | None:
        match = re.search(r"elementId:([^\\\s]+)", output)
        return match.group(1) if match else None