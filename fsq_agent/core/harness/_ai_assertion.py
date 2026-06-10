from typing import Protocol, runtime_checkable


@runtime_checkable
class AIAssertionEvaluator(Protocol):
    def evaluate(
        self,
        *,
        prompt: str,
        screenshot: bytes,
        ui_tree: dict[str, object] | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        ...


def normalize_ai_assertion_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        return {"verdict": "inconclusive", "reasoning": "AI assertion evaluator returned a non-mapping result."}
    verdict = result.get("verdict")
    normalized_verdict = verdict if verdict in {"passed", "failed", "inconclusive"} else "inconclusive"
    output: dict[str, object] = dict(result)
    output["verdict"] = normalized_verdict
    return output
