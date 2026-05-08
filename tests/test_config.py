from pathlib import Path

import pytest

from auto_test_agent.config import load_settings, validate_runtime_settings
from auto_test_agent.models import ConfigurationError


def test_load_settings_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
agent:
  name: test-agent
cli_tools:
  - name: echo
    command: python
observation:
  screenshot:
    enabled: false
  ui_tree:
    enabled: false
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.agent.name == "test-agent"
    assert settings.cli_tools[0].name == "echo"
    assert settings.output.logs_dir.exists()


def test_load_settings_accepts_mcp_tool_validation_policy(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
mcp_tool_validation:
  enabled: true
  invalid_tool_policy: fail_fast
  strict_schema: false
  unsupported_schema_keywords:
    - propertyNames
  fail_when_all_tools_filtered: false
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.mcp_tool_validation.invalid_tool_policy == "fail_fast"
    assert settings.mcp_tool_validation.strict_schema is False
    assert settings.mcp_tool_validation.unsupported_schema_keywords == ["propertyNames"]
    assert settings.mcp_tool_validation.fail_when_all_tools_filtered is False


def test_openai_agents_endpoint_is_normalized(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: false
  base_url: https://edgeqa-resource.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.openai_agents.base_url == "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/"


def test_validate_runtime_settings_requires_api_key_when_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: true
  api_key_env: AUTO_TEST_AGENT_MISSING_KEY
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError):
        validate_runtime_settings(settings)


def test_validate_runtime_settings_requires_openai_agents_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: false
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError, match="OpenAI Agents SDK must be enabled"):
        validate_runtime_settings(settings)


def test_validate_runtime_settings_requires_shell_allowlist_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: true
shell:
  enabled: true
  mode: allowlist
  command_allowlist: []
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError, match="allowlist cannot be empty"):
        validate_runtime_settings(settings)


def test_validate_runtime_settings_allows_shell_allow_all(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: true
shell:
  enabled: true
  mode: allow_all
  command_allowlist: []
  working_dir: .
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    validate_runtime_settings(settings)


def test_load_settings_loads_dotenv_from_config_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: true
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("AZURE_OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    settings = load_settings(config_path)

    validate_runtime_settings(settings)
    assert settings.openai_agents.api_key_env == "AZURE_OPENAI_API_KEY"


def test_load_settings_dotenv_does_not_override_existing_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "from-process")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: true
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("AZURE_OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    load_settings(config_path)

    assert __import__("os").environ["AZURE_OPENAI_API_KEY"] == "from-process"


def test_load_settings_rejects_invalid_dotenv_line(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    (tmp_path / ".env").write_text("not-a-key-value-line\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid .env line"):
        load_settings(config_path)


def test_validate_runtime_settings_rejects_placeholder_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTO_TEST_AGENT_PLACEHOLDER_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
openai_agents:
  enabled: true
  api_key_env: AUTO_TEST_AGENT_PLACEHOLDER_KEY
output:
  logs_dir: logs
  reports_dir: reports
  screenshots_dir: screenshots
  traces_dir: traces
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "AUTO_TEST_AGENT_PLACEHOLDER_KEY=replace-with-your-azure-openai-api-key\n",
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError, match="placeholder"):
        validate_runtime_settings(settings)