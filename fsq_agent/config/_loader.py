from pathlib import Path
from typing import Any
import os

import yaml
from pydantic import ValidationError

from fsq_agent.config._paths import resolve_runtime_paths
from fsq_agent.config._settings import Settings
from fsq_agent.models import ConfigurationError


DEFAULT_CONFIG_PATHS = (Path("config.yaml"), Path("config.yml"), Path("config.example.yaml"))
DEFAULT_ENV_PATH = Path(".env")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as config_file:
            data = yaml.safe_load(config_file) or {}
    except OSError as exc:
        raise ConfigurationError("Unable to read configuration file.", context={"path": str(path)}) from exc
    if not isinstance(data, dict):
        raise ConfigurationError("Configuration file must contain a YAML mapping.", context={"path": str(path)})
    return data


def _find_default_config() -> Path | None:
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path
    return None


def load_settings(path: str | Path | None = None, workspace: str | Path | None = None) -> Settings:
    config_path = Path(path) if path is not None else _find_default_config()
    _load_env_files(config_path)
    data = _read_yaml(config_path) if config_path else {}
    try:
        settings = Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError("Invalid configuration.", context={"errors": exc.errors()}) from exc
    if workspace is not None:
        settings.workspace.root_dir = Path(workspace)
    _normalize_openai_provider_settings(settings, data)
    base_dir = config_path.parent if config_path is not None else Path.cwd()
    resolve_runtime_paths(settings, base_dir)
    return settings


def _load_env_files(config_path: Path | None) -> None:
    candidates = [DEFAULT_ENV_PATH]
    if config_path is not None:
        config_env_path = config_path.parent / DEFAULT_ENV_PATH
        if config_env_path not in candidates:
            candidates.append(config_env_path)
    for env_path in candidates:
        _load_env_file(env_path)


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigurationError("Unable to read .env file.", context={"path": str(path)}) from exc
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ConfigurationError(
                "Invalid .env line; expected KEY=VALUE.",
                context={"path": str(path), "line": line_number},
            )
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ConfigurationError(
                "Invalid .env line; key cannot be empty.",
                context={"path": str(path), "line": line_number},
            )
        os.environ.setdefault(key, _strip_env_value(value.strip()))


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _normalize_openai_provider_settings(settings: Settings, data: dict[str, Any]) -> None:
    if settings.openai_agents.provider == "github_copilot":
        if not _openai_model_configured(data):
            settings.openai_agents.model = "gpt-5.5"
        return
    base_url = settings.openai_agents.base_url.strip()
    if "/openai/responses" in base_url:
        base_url = base_url.split("/openai/responses", 1)[0] + "/openai/v1/"
    elif "/openai/v1" in base_url:
        base_url = base_url.split("/openai/v1", 1)[0] + "/openai/v1/"
    elif base_url.endswith(".openai.azure.com") or base_url.endswith(".cognitiveservices.azure.com"):
        base_url = base_url.rstrip("/") + "/openai/v1/"
    settings.openai_agents.base_url = base_url


def _openai_model_configured(data: dict[str, Any]) -> bool:
    openai_agents = data.get("openai_agents")
    return isinstance(openai_agents, dict) and "model" in openai_agents


def validate_runtime_settings(settings: Settings) -> None:
    _validate_openai_provider_settings(settings)
    _validate_android_harness_settings(settings)


def validate_strict_core_settings(settings: Settings, requires_ai_assertion: bool = False) -> None:
    _validate_android_harness_settings(settings)
    if requires_ai_assertion:
        _validate_openai_provider_settings(settings)


def _validate_openai_provider_settings(settings: Settings) -> None:
    if not settings.openai_agents.model.strip():
        raise ConfigurationError("OpenAI Agents SDK model deployment name is required.")
    if settings.openai_agents.provider == "azure_openai" and not settings.openai_agents.base_url.endswith("/openai/v1/"):
        raise ConfigurationError(
            "Azure OpenAI base URL must use the /openai/v1/ form.",
            context={"base_url": settings.openai_agents.base_url},
        )
    api_key = os.getenv(settings.openai_agents.api_key_env)
    if settings.openai_agents.provider == "azure_openai" and settings.openai_agents.fail_without_api_key and not api_key:
        raise ConfigurationError(
            "Azure OpenAI API key environment variable is not set.",
            context={"api_key_env": settings.openai_agents.api_key_env},
        )
    if (
        settings.openai_agents.provider == "azure_openai"
        and settings.openai_agents.fail_without_api_key
        and api_key
        and api_key.lower().startswith("replace-with")
    ):
        raise ConfigurationError(
            "Azure OpenAI API key environment variable still contains a placeholder value.",
            context={"api_key_env": settings.openai_agents.api_key_env},
        )


def _validate_android_harness_settings(settings: Settings) -> None:
    if settings.harness.platform != "android":
        raise ConfigurationError(
            "Unsupported harness platform.",
            context={"platform": settings.harness.platform, "supported": ["android"]},
        )
    if settings.harness.android.backend != "uiautomator2":
        raise ConfigurationError(
            "Unsupported Android harness backend.",
            context={"backend": settings.harness.android.backend, "supported": ["uiautomator2"]},
        )