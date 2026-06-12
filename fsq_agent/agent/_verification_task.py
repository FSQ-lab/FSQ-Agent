import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from fsq_agent.models import AgentFinalOutput, StepResult, Task, ToolCallRecord, VerificationMode

from fsq_agent.agent._structured_output import coerce_agent_final_output


class VerificationEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "verification_evidence_v1"
    verification_mode: VerificationMode = "normal"
    task: dict[str, Any]
    blocking_criteria: list[dict[str, Any]] = Field(default_factory=list)
    nonblocking_criteria: list[dict[str, Any]] = Field(default_factory=list)
    agent_claims: dict[str, Any] | None = None
    execution_steps: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)


class VerificationEvidenceBuilder:
    def __init__(self, artifact_preview_chars: int = 12000) -> None:
        self.artifact_preview_chars = artifact_preview_chars

    def build(
        self,
        task: Task,
        results: list[StepResult],
        events_path: Path | None = None,
        image_root: Path | None = None,
        mode: VerificationMode = "normal",
    ) -> VerificationEvidenceBundle:
        _ = image_root
        report_dir = events_path.parent if events_path else None
        tool_calls = self._load_tool_calls(events_path)
        blocking_criteria = task.blocking_verification_criteria(mode)
        blocking_texts = {criterion.text for criterion in blocking_criteria}
        all_criteria = task.required_verification_criteria()
        return VerificationEvidenceBundle(
            verification_mode=mode,
            task=task.model_dump(mode="json"),
            blocking_criteria=[criterion.model_dump(mode="json") for criterion in blocking_criteria],
            nonblocking_criteria=[criterion.model_dump(mode="json") for criterion in all_criteria if criterion.text not in blocking_texts],
            agent_claims=self._agent_claims(results),
            execution_steps=[self._step_record(step) for step in results],
            tool_calls=tool_calls,
            artifacts=self._load_artifacts(report_dir),
            instructions=[
                "Use only the supplied evidence bundle.",
                "Treat agent_claims as claims, not proof.",
                "Mark a criterion satisfied only when supplied events, tool outputs, or artifact excerpts support it.",
                "Mark a criterion unmet only when supplied evidence proves it did not happen or the required final state is false.",
                "If evidence is missing, truncated, ambiguous, or outside the supplied bundle, mark the criterion unknown by leaving it out of both satisfied_criteria and unmet_criteria and use status=inconclusive.",
                "For visual assertions such as assertWithAI, do not re-inspect screenshot pixels. Verify that execution evidence contains the harness-owned AI assertion tool result, including verdict metadata and screenshot artifact references, and that no supplied evidence contradicts that result.",
                "Do not depend on fixed key-action text formats; infer the intended requirement from the task/case content provided in the bundle.",
                "Apply verification_mode only to final status. In strict mode, all required goal, assertion, and operation criteria are blocking. In normal mode, only goal and assertion criteria are blocking. In goal mode, only goal criteria are blocking.",
                "Nonblocking criteria may be discussed as evidence or diagnostics, but they must not make the final status failed or inconclusive when every blocking criterion is satisfied.",
            ],
        )

    def build_json(self, task: Task, results: list[StepResult], events_path: Path | None = None, mode: VerificationMode = "normal") -> str:
        return self.build(task, results, events_path, mode=mode).model_dump_json(indent=2)

    def build_model_input(
        self,
        task: Task,
        results: list[StepResult],
        events_path: Path | None = None,
        image_root: Path | None = None,
        mode: VerificationMode = "normal",
    ) -> str:
        bundle = self.build(task, results, events_path, image_root, mode)
        return bundle.model_dump_json(indent=2)

    def _agent_claims(self, results: list[StepResult]) -> dict[str, Any] | None:
        runner_steps = [step for step in results if step.tool_name == "openai_agents.runner"]
        if not runner_steps:
            return None
        raw_output = runner_steps[-1].tool_output or runner_steps[-1].actual_outcome
        payload = raw_output if isinstance(raw_output, AgentFinalOutput) else coerce_agent_final_output(raw_output)
        if payload:
            return payload.model_dump(mode="json")
        return {"raw_output": str(raw_output)}

    def _step_record(self, step: StepResult) -> dict[str, Any]:
        return {
            "step_id": step.step_id,
            "status": step.status,
            "source": step.tool_name or "runtime",
            "outcome": step.actual_outcome,
            "error": step.error,
            "duration_ms": step.duration_ms,
            "screenshot_path": str(step.screenshot_path) if step.screenshot_path else None,
            "tool_output": self._compact_value(step.tool_output),
        }

    def _load_tool_calls(self, events_path: Path | None) -> list[dict[str, Any]]:
        if not events_path or not events_path.exists():
            return []
        starts: dict[str, dict[str, Any]] = {}
        calls: list[ToolCallRecord] = []
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
            start_payload = start.get("payload") if isinstance(start.get("payload"), dict) else {}
            event_payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            tool_name = str(start.get("tool_name") or event.get("tool_name") or "unknown")
            calls.append(
                ToolCallRecord(
                    tool_call_id=call_id,
                    tool_name=tool_name,
                    tool_origin=self._tool_origin(tool_name, start_payload.get("tool_origin") or event_payload.get("tool_origin")),
                    status="failed" if event_type == "tool_call_failed" else "completed",
                    arguments=start.get("tool_arguments"),
                    output_preview=event.get("tool_output_preview"),
                    artifact_path=event_payload.get("artifact_path"),
                    error=event.get("message") if event_type == "tool_call_failed" else None,
                    started_sequence=start.get("sequence"),
                    completed_sequence=event.get("sequence"),
                    started_at=start.get("timestamp"),
                    completed_at=event.get("timestamp"),
                    duration_ms=event.get("duration_ms"),
                )
            )
        return [call.model_dump(mode="json") for call in calls]

    def _load_artifacts(self, report_dir: Path | None) -> list[dict[str, Any]]:
        if not report_dir:
            return []
        artifacts_dir = report_dir / "artifacts" / "tools"
        if not artifacts_dir.exists():
            return []
        artifacts: list[dict[str, Any]] = []
        for path in sorted(artifacts_dir.glob("*.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                artifacts.append({"path": str(path), "error": str(exc)})
                continue
            artifacts.append(
                {
                    "path": str(path),
                    "content_chars": len(text),
                    "preview": self._preview(text),
                }
            )
        return artifacts

    def _preview(self, text: str) -> str:
        limit = self.artifact_preview_chars
        if len(text) <= limit:
            return text
        head = text[:limit]
        tail = text[-2000:] if len(text) > limit + 2000 else ""
        return f"{head}\n...[truncated {len(text) - len(head) - len(tail)} chars]...\n{tail}"

    def _compact_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list, str, int, float, bool)):
            text = json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, str) else value
            return self._preview(text) if len(text) > self.artifact_preview_chars else value
        return self._preview(str(value))

    def _tool_origin(self, tool_name: str, explicit_origin: Any) -> str:
        if explicit_origin in {"harness", "common", "runtime", "unknown"}:
            return str(explicit_origin)
        if tool_name in {"read_file", "write_file", "get_runtime_secret", "search_artifact", "read_artifact_slice", "wait_ms"}:
            return "common"
        if tool_name in {"read_knowledge_index", "read_knowledge_page"}:
            return "runtime"
        if tool_name == "unknown":
            return "unknown"
        return "harness"


VERIFICATION_AGENT_INSTRUCTIONS = """You are an evidence-based automation result verifier.

Your only job is to determine whether the completed automation run satisfied the supplied task/case requirements.

Rules:
- Use only the evidence bundle in the input. Do not assume facts that are not present in task text, execution records, tool outputs, or artifact excerpts.
- Treat the main agent's final output as a claim, not proof.
- Do not rely on hard-coded key-action formats. The case loader may change action syntax and fields; infer the intended requirement from the supplied task and acceptance criteria.
- Apply the supplied verification_mode when deciding the final status: strict means all required goal/assertion/operation criteria are blocking; normal means only required goal/assertion criteria are blocking; goal means only required goal criteria are blocking.
- Always use the supplied blocking_criteria list as the final blocking set. Nonblocking criteria can support diagnostics but must not by themselves cause failed or inconclusive status.
- Mark criteria as satisfied only when the supplied evidence supports them.
- Mark criteria as unmet only when the supplied evidence proves the required action/state did not occur or a permanent execution failure prevents it.
- If evidence is insufficient or ambiguous, leave the criterion out of satisfied_criteria and unmet_criteria, explain it in evidence/errors, and use status=inconclusive unless another criterion is proven unmet.
- For visual assertions such as assertWithAI, do not re-inspect screenshot pixels. The execution stage evaluates authored visual assertions through the harness-owned platform AI assertion action. Verify that execution records contain the harness AI assertion result, verdict metadata, and screenshot artifact reference, that the main agent's structured output reports the corresponding result, and that no supplied evidence contradicts that result.
- Final status must be success only when every required criterion is satisfied; failed only when at least one required criterion is proven unmet; inconclusive when there are unknown criteria and no proven unmet criteria.

Return only the configured structured final output. Do not perform external actions.
"""