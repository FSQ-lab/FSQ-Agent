import json
import re
from typing import Any


JSON_BLOCK_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def parse_structured_output(output: str) -> dict[str, Any] | None:
    candidate = output.strip()
    block_match = JSON_BLOCK_PATTERN.search(candidate)
    if block_match:
        candidate = block_match.group(1)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]