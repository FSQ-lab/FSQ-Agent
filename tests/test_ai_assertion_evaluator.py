import base64
import json

import pytest

from fsq_agent.agent import OpenAIAssertionEvaluator
from fsq_agent.config import Settings
from fsq_agent.models import OpenAIAgentsSettings


class FakeResponseText:
    def __init__(self, parsed: dict[str, object]) -> None:
        self.parsed = parsed


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def parse(self, **kwargs: object) -> FakeResponseText:
        self.calls.append(kwargs)
        return FakeResponseText({"verdict": "passed", "reasoning": "The page is visible."})


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _settings(model: str = "gpt-test") -> Settings:
    return Settings(openai_agents=OpenAIAgentsSettings(model=model, fail_without_api_key=False))


def test_openai_ai_assertion_evaluator_sends_screenshot_and_context() -> None:
    client = FakeOpenAIClient()
    evaluator = OpenAIAssertionEvaluator(_settings(), client_factory=lambda _settings: client)

    result = evaluator.evaluate(
        prompt="Verify the Bing homepage is shown.",
        screenshot=b"png-bytes",
        ui_tree={"nodes": [{"text": "Bing"}]},
        metadata={"step_id": "step-1"},
    )

    assert result == {"verdict": "passed", "reasoning": "The page is visible."}
    assert client.closed is True
    call = client.responses.calls[0]
    assert call["model"] == "gpt-test"
    response_format = call["text"]["format"]
    assert response_format["name"] == "ai_visual_assertion_result"
    assert response_format["schema"]["required"] == ["verdict", "reasoning"]

    message = call["input"][0]
    assert message["role"] == "user"
    text_part = message["content"][0]
    image_part = message["content"][1]
    assert "Verify the Bing homepage is shown." in text_part["text"]
    assert "step-1" in text_part["text"]
    assert "Bing" in text_part["text"]
    assert image_part["type"] == "input_image"
    assert image_part["image_url"] == "data:image/png;base64," + base64.b64encode(b"png-bytes").decode("ascii")


def test_openai_ai_assertion_evaluator_normalizes_invalid_model_output() -> None:
    class InvalidResponses(FakeResponses):
        def parse(self, **kwargs: object) -> FakeResponseText:
            return FakeResponseText({"verdict": "maybe", "reasoning": "unclear"})

    client = FakeOpenAIClient()
    client.responses = InvalidResponses()
    evaluator = OpenAIAssertionEvaluator(_settings(), client_factory=lambda _settings: client)

    result = evaluator.evaluate(prompt="Check UI", screenshot=b"png", ui_tree=None, metadata={})

    assert result == {"verdict": "inconclusive", "reasoning": "unclear"}


def test_openai_ai_assertion_evaluator_handles_non_mapping_parsed_output() -> None:
    class TextResponses(FakeResponses):
        def parse(self, **kwargs: object) -> FakeResponseText:
            return FakeResponseText("not-json")  # type: ignore[arg-type]

    client = FakeOpenAIClient()
    client.responses = TextResponses()
    evaluator = OpenAIAssertionEvaluator(_settings(), client_factory=lambda _settings: client)

    result = evaluator.evaluate(prompt="Check UI", screenshot=b"png", ui_tree=None, metadata={})

    assert result["verdict"] == "inconclusive"
    assert "non-mapping" in str(result["reasoning"])


def test_openai_ai_assertion_evaluator_rejects_empty_prompt() -> None:
    evaluator = OpenAIAssertionEvaluator(_settings(), client_factory=lambda _settings: FakeOpenAIClient())

    with pytest.raises(ValueError, match="prompt"):
        evaluator.evaluate(prompt=" ", screenshot=b"png", ui_tree=None, metadata={})


def test_openai_ai_assertion_evaluator_parse_fallback_for_raw_json() -> None:
    class RawResponse:
        output_text = json.dumps({"verdict": "failed", "reasoning": "Missing expected content."})

    class RawResponses(FakeResponses):
        def parse(self, **kwargs: object) -> RawResponse:
            return RawResponse()

    client = FakeOpenAIClient()
    client.responses = RawResponses()
    evaluator = OpenAIAssertionEvaluator(_settings(), client_factory=lambda _settings: client)

    result = evaluator.evaluate(prompt="Check UI", screenshot=b"png", ui_tree=None, metadata={})

    assert result == {"verdict": "failed", "reasoning": "Missing expected content."}
