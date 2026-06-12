from pathlib import Path

from fsq_agent.models import AgentFinalOutput, StepResult, Task, VerificationMode, VerificationResult

from fsq_agent.agent._structured_output import coerce_agent_final_output


class Verifier:
    async def verify(
        self,
        task: Task,
        results: list[StepResult],
        events_path: Path | None = None,
        mode: VerificationMode = "normal",
    ) -> VerificationResult:
        _ = events_path
        verifier_steps = [step for step in results if step.tool_name == "openai_agents.verifier"]
        runner_steps = [step for step in results if step.tool_name == "openai_agents.runner"]
        sdk_steps = verifier_steps or runner_steps
        if sdk_steps:
            return self._verify_first_parseable_sdk_result(task, sdk_steps, require_parseable=bool(verifier_steps), mode=mode)

        failed_steps = [step for step in results if step.status == "failed"]
        if failed_steps:
            return VerificationResult(
                status="failed",
                summary="One or more execution steps failed.",
                unmet_criteria=self._blocking_texts(task, mode) or ["The task flow did not complete successfully."],
                diagnostics=[step.error or step.actual_outcome for step in failed_steps],
            )
        return VerificationResult(
            status="inconclusive",
            summary="Execution completed, but final acceptance criteria require an LLM verifier or domain-specific checks.",
            satisfied_criteria=[],
            unmet_criteria=self._blocking_texts(task, mode) or ["No derived acceptance criteria were reported."],
            diagnostics=["Verifier avoids claiming UI task success without direct evidence."],
        )

    def _verify_first_parseable_sdk_result(
        self,
        task: Task,
        steps: list[StepResult],
        *,
        require_parseable: bool = False,
        mode: VerificationMode = "normal",
    ) -> VerificationResult:
        invalid_diagnostics: list[str] = []
        for step in reversed(steps):
            if self._parse_final_output(step.actual_outcome) is None and self._parse_final_output(step.tool_output) is None:
                invalid_diagnostics.append(step.error or step.actual_outcome)
                continue
            result = self._verify_sdk_result(task, step, mode)
            if invalid_diagnostics:
                result.diagnostics.extend(invalid_diagnostics)
            return result
        return VerificationResult(
            status="inconclusive",
            summary="Verifier agent did not produce valid verification JSON." if require_parseable else "No verifier or runner step produced valid verification JSON.",
            satisfied_criteria=[],
            unmet_criteria=[],
            diagnostics=invalid_diagnostics or ["No structured verification output was available."],
        )

    def _verify_sdk_result(self, task: Task, step: StepResult, mode: VerificationMode) -> VerificationResult:
        payload = self._parse_final_output(step.tool_output) or self._parse_final_output(step.actual_outcome)
        if payload is None:
            return VerificationResult(
                status="inconclusive",
                summary="OpenAI Agents SDK completed, but the final output was not valid verification JSON.",
                satisfied_criteria=[],
                unmet_criteria=self._blocking_texts(task, mode) or ["No derived acceptance criteria were reported."],
                diagnostics=[step.actual_outcome],
            )

        return self._apply_mode(task, payload, step, mode)

    def _apply_mode(self, task: Task, payload: AgentFinalOutput, step: StepResult, mode: VerificationMode) -> VerificationResult:
        status = payload.status
        satisfied_criteria = list(payload.satisfied_criteria)
        unmet_criteria = list(payload.unmet_criteria)
        evidence = list(payload.evidence)
        errors = list(payload.errors)
        plan_updates = list(payload.plan_updates)
        summary = payload.summary or "Task verification completed."

        diagnostics = [*evidence, *plan_updates, *errors]
        if not diagnostics:
            diagnostics = [step.actual_outcome]

        blocking_criteria = self._blocking_texts(task, mode)
        if blocking_criteria:
            blocking_satisfied = [criterion for criterion in blocking_criteria if self._contains_criterion(satisfied_criteria, criterion)]
            blocking_unmet = [criterion for criterion in blocking_criteria if self._contains_criterion(unmet_criteria, criterion)]
            blocking_unknown = [criterion for criterion in blocking_criteria if criterion not in blocking_satisfied and criterion not in blocking_unmet]
            nonblocking_unmet = [criterion for criterion in unmet_criteria if not self._contains_criterion(blocking_criteria, criterion)]
            if nonblocking_unmet:
                diagnostics.append(f"Non-blocking criteria reported unmet under verification mode `{mode}`: {', '.join(nonblocking_unmet)}")

            if blocking_unmet:
                status = "failed"
                unmet_criteria = blocking_unmet
                satisfied_criteria = blocking_satisfied
            elif blocking_unknown:
                status = "inconclusive"
                unmet_criteria = blocking_unknown
                satisfied_criteria = blocking_satisfied
            else:
                status = "success"
                unmet_criteria = []
                satisfied_criteria = blocking_satisfied

        return VerificationResult(
            status=status,
            summary=summary,
            satisfied_criteria=satisfied_criteria,
            unmet_criteria=unmet_criteria,
            diagnostics=diagnostics,
        )

    def _parse_final_output(self, output: object) -> AgentFinalOutput | None:
        return coerce_agent_final_output(output)

    def _blocking_texts(self, task: Task, mode: VerificationMode) -> list[str]:
        return [criterion.text for criterion in task.blocking_verification_criteria(mode)]

    def _contains_criterion(self, values: list[str], criterion: str) -> bool:
        normalized = self._normalize_criterion(criterion)
        return any(self._normalize_criterion(value) == normalized for value in values)

    def _normalize_criterion(self, value: str) -> str:
        return " ".join(value.split()).casefold()
