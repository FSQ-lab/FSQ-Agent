from dataclasses import dataclass, field
from typing import Any
import os

from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError


@dataclass(frozen=True)
class ProviderClientConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    default_headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def build_azure_openai_client_config(settings: Settings) -> ProviderClientConfig:
    openai_settings = settings.openai_agents
    api_key = os.getenv(openai_settings.api_key_env)
    if not api_key:
        raise ConfigurationError(
            "Azure OpenAI API key environment variable is not set.",
            context={"api_key_env": openai_settings.api_key_env},
        )
    if api_key.lower().startswith("replace-with"):
        raise ConfigurationError(
            "Azure OpenAI API key environment variable still contains a placeholder value.",
            context={"api_key_env": openai_settings.api_key_env},
        )
    base_url = openai_settings.base_url.strip()
    if not base_url.endswith("/openai/v1/"):
        raise ConfigurationError(
            "Azure OpenAI base URL must use the /openai/v1/ form.",
            context={"base_url": base_url},
        )
    return ProviderClientConfig(
        provider="azure_openai",
        model=openai_settings.model,
        api_key=api_key,
        base_url=base_url,
        metadata={"endpoint_family": "azure_openai"},
    )