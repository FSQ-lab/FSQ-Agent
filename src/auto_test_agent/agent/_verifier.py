from typing import Any

from auto_test_agent.models import StepResult, Task, VerificationResult

from auto_test_agent.agent._structured_output import coerce_string_list, parse_structured_output


class Verifier:
    async def verify(self, task: Task, results: list[StepResult]) -> VerificationResult:
        failed_steps = [step for step in results if step.status == "failed"]
        if failed_steps:
            return VerificationResult(
                status="failed",
                summary="One or more execution steps failed.",
                unmet_criteria=task.acceptance_criteria or ["The task flow did not complete successfully."],
                diagnostics=[step.error or step.actual_outcome for step in failed_steps],
            )
        sdk_steps = [step for step in results if step.tool_name == "openai_agents.runner"]
        if sdk_steps:
            return self._verify_sdk_result(task, sdk_steps[-1])
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

        raw_status = str(payload.get("status", "inconclusive")).lower()
        status = raw_status if raw_status in {"success", "failed", "inconclusive"} else "inconclusive"
        satisfied_criteria = coerce_string_list(payload.get("satisfied_criteria"))
        unmet_criteria = coerce_string_list(payload.get("unmet_criteria"))
        evidence = coerce_string_list(payload.get("evidence"))
        errors = coerce_string_list(payload.get("errors"))
        plan_updates = coerce_string_list(payload.get("plan_updates"))
        summary = str(payload.get("summary") or "Task verification completed.")
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

    def _parse_final_output(self, output: str) -> dict[str, Any] | None:
        return parse_structured_output(output)

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