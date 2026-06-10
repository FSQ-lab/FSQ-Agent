from __future__ import annotations

import base64
import json
import os
from typing import Any, Callable

from fsq_agent.agent._copilot_provider import build_copilot_async_openai_client
from fsq_agent.config import Settings, validate_runtime_settings
from fsq_agent.models import ConfigurationError


AI_ASSERTION_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "name": "ai_visual_assertion_result",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verdict": {"type": "string", "enum": ["passed", "failed", "inconclusive"]},
            "reasoning": {"type": "string"},
        },
        "required": ["verdict", "reasoning"],
    },
}


class OpenAIAssertionEvaluator:
    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[Settings], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.client_factory = client_factory or _build_openai_client

    def evaluate(
        self,
        *,
        prompt: str,
        screenshot: bytes,
        ui_tree: dict[str, object] | None,
        metadata: dict[str, object],
    ) -> dict[str, object]:
        normalized_prompt = prompt.strip()
        if not normalized_prompt:
            raise ValueError("assertWithAI prompt cannot be empty.")
        validate_runtime_settings(self.settings)
        client = self.client_factory(self.settings)
        try:
            response = client.responses.parse(
                model=self.settings.openai_agents.model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": self._build_text(normalized_prompt, ui_tree, metadata)},
                            {"type": "input_image", "image_url": self._data_url(screenshot)},
                        ],
                    }
                ],
                text={"format": AI_ASSERTION_RESPONSE_FORMAT},
            )
            return _normalize_ai_assertion_result(self._parsed_payload(response))
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _build_text(
        self,
        prompt: str,
        ui_tree: dict[str, object] | None,
        metadata: dict[str, object],
    ) -> str:
        return (
            "Evaluate this authored FSQ visual assertion from the provided screenshot. "
            "Return only the requested structured verdict. Do not propose recovery actions, "
            "locator changes, or testcase edits.\n\n"
            f"Assertion prompt:\n{prompt}\n\n"
            f"Runner metadata:\n{self._json(metadata)}\n\n"
            f"Current UI tree, if available:\n{self._json(ui_tree or {})}"
        )

    def _data_url(self, screenshot: bytes) -> str:
        return "data:image/png;base64," + base64.b64encode(screenshot).decode("ascii")

    def _json(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    def _parsed_payload(self, response: object) -> object:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            try:
                return json.loads(output_text)
            except json.JSONDecodeError:
                pass
        parsed = getattr(getattr(response, "output_parsed", None), "parsed", None)
        if parsed is not None:
            return parsed
        output_parsed = getattr(response, "output_parsed", None)
        if output_parsed is not None:
            return output_parsed
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                parsed = getattr(content, "parsed", None)
                if parsed is not None:
                    return parsed
        return getattr(response, "parsed", None)


def _build_openai_client(settings: Settings) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise ConfigurationError("openai package is required for AI assertions.") from exc
    if settings.openai_agents.provider == "github_copilot":
        return build_copilot_async_openai_client(OpenAI, settings.workspace.root_dir)
    return OpenAI(
        api_key=os.environ[settings.openai_agents.api_key_env],
        base_url=settings.openai_agents.base_url,
    )


def _normalize_ai_assertion_result(result: object) -> dict[str, object]:
    if not isinstance(result, dict):
        return {"verdict": "inconclusive", "reasoning": "AI assertion evaluator returned a non-mapping result."}
    verdict = result.get("verdict")
    normalized_verdict = verdict if verdict in {"passed", "failed", "inconclusive"} else "inconclusive"
    output: dict[str, object] = dict(result)
    output["verdict"] = normalized_verdict
    return output
