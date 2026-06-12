from pathlib import Path

import pytest

from fsq_agent.config import load_settings, validate_runtime_settings, validate_strict_core_settings
from fsq_agent.models import ConfigurationError


def _base_config(tmp_path: Path, body: str = "") -> str:
    return f"""
workspace:
  root_dir: {tmp_path.as_posix()}/workspace
cases:
  dir: cases
output:
  root_dir: output
  runs_dir: runs
{body}
"""


def test_load_settings_from_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
agent:
  name: test-agent
cli_tools:
  - name: echo
    command: python
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.agent.name == "test-agent"
    assert settings.verification.mode == "normal"
    assert settings.cli_tools[0].name == "echo"
    assert settings.workspace.root_dir == tmp_path / "workspace"
    assert (settings.workspace.root_dir / ".fsq-agent-workspace").exists()
    assert settings.output.root_dir == tmp_path / "workspace" / "output"
    assert settings.output.runs_dir.exists()
    assert settings.cases.dir == tmp_path / "cases"


def test_load_settings_rejects_non_empty_unmarked_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "user-file.txt").write_text("do not own this", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_base_config(tmp_path), encoding="utf-8")

    with pytest.raises(ConfigurationError, match="not marked"):
        load_settings(config_path)


def test_load_settings_accepts_harness_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
harness:
  platform: android
  android:
    backend: uiautomator2
    app_id: com.example.app
    serial: emulator-5554
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.harness.platform == "android"
    assert settings.harness.android.backend == "uiautomator2"
    assert settings.harness.android.app_id == "com.example.app"
    assert settings.harness.android.serial == "emulator-5554"


def test_load_settings_accepts_runtime_secret_allowlist(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
runtime_secrets:
  allowed_env_names:
    - TEST_ACCOUNT_EMAIL
    - TEST_ACCOUNT_PASSWORD
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.runtime_secrets.allowed_env_names == ["TEST_ACCOUNT_EMAIL", "TEST_ACCOUNT_PASSWORD"]


def test_load_settings_accepts_pre_plan_knowledge_dir(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
knowledge_dir: ./knowledge
pre_plan:
  knowledge_dir: ./knowledge/project_android_v1
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.knowledge_dir == tmp_path / "knowledge"
    assert settings.pre_plan.knowledge_dir == tmp_path / "knowledge" / "project_android_v1"


def test_load_settings_accepts_verification_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
verification:
  mode: strict
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.verification.mode == "strict"


def test_load_settings_rejects_invalid_verification_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
verification:
  mode: loose
""",
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError, match="Invalid configuration"):
        load_settings(config_path)


def test_openai_agents_endpoint_is_normalized(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  base_url: https://edgeqa-resource.cognitiveservices.azure.com/openai/responses?api-version=2025-04-01-preview
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.openai_agents.base_url == "https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/"


def test_github_copilot_provider_disables_responses_and_skips_azure_key(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
  config_path = tmp_path / "config.yaml"
  config_path.write_text(
    _base_config(
      tmp_path,
      """
openai_agents:
  provider: github_copilot
""",
    ),
    encoding="utf-8",
  )

  settings = load_settings(config_path)

  validate_runtime_settings(settings)
  assert settings.openai_agents.provider == "github_copilot"
  assert settings.openai_agents.model == "gpt-5.5"


def test_github_copilot_provider_preserves_explicit_model(tmp_path: Path) -> None:
  config_path = tmp_path / "config.yaml"
  config_path.write_text(
    _base_config(
      tmp_path,
      """
openai_agents:
  provider: github_copilot
  model: custom-copilot-model
""",
    ),
    encoding="utf-8",
  )

  settings = load_settings(config_path)

  assert settings.openai_agents.model == "custom-copilot-model"


def test_load_settings_rejects_invalid_provider(tmp_path: Path) -> None:
  config_path = tmp_path / "config.yaml"
  config_path.write_text(
    _base_config(
      tmp_path,
      """
openai_agents:
  provider: local_llm
""",
    ),
    encoding="utf-8",
  )

  with pytest.raises(ConfigurationError, match="Invalid configuration"):
    load_settings(config_path)


def test_load_settings_accepts_context_and_tool_output_policy(tmp_path: Path) -> None:
    agent_template = tmp_path / "agent.j2"
    task_template = tmp_path / "task.j2"
    custom_instructions = tmp_path / "custom-instructions.md"
    agent_template.write_text("Agent {{ variables.voice }}", encoding="utf-8")
    task_template.write_text("Task {{ task.id }}", encoding="utf-8")
    custom_instructions.write_text("Prefer semantic UI assertions before visual fallback.", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  prompt:
    agent_template_path: ./agent.j2
    task_template_path: ./task.j2
    custom_instructions_path: ./custom-instructions.md
    variables:
      voice: concise
  context_trimming:
    enabled: true
    recent_turns: 3
    max_tool_output_chars: 12000
    preview_chars: 1500
    trimmable_tools: [run_cli_tool]
  local_tool_output:
    artifact_enabled: true
    always_write_artifact: true
    artifact_subdir: artifacts/tools
    recent_full_output_count: 4
    full_output_max_chars: 40000
    historical_output_mode: artifact_reference
    historical_preview_chars: 1500
    model_response_max_chars: 5000
""",
        ),
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings.openai_agents.context_trimming.recent_turns == 3
    assert settings.openai_agents.prompt.agent_template_path == agent_template.resolve()
    assert settings.openai_agents.prompt.task_template_path == task_template.resolve()
    assert settings.openai_agents.prompt.custom_instructions_path == custom_instructions.resolve()
    assert settings.openai_agents.prompt.variables == {"voice": "concise"}
    assert settings.openai_agents.context_trimming.trimmable_tools == ["run_cli_tool"]
    assert settings.openai_agents.local_tool_output.recent_full_output_count == 4
    assert settings.openai_agents.local_tool_output.full_output_max_chars == 40000


def test_load_settings_uses_default_harness(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_base_config(tmp_path), encoding="utf-8")

    settings = load_settings(config_path)

    assert settings.harness.platform == "android"
    assert settings.harness.android.backend == "uiautomator2"
    assert settings.harness.android.app_id is None


def test_validate_runtime_settings_requires_api_key_when_enabled(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  api_key_env: FSQ_AGENT_MISSING_KEY
""",
        ),
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError):
        validate_runtime_settings(settings)


def test_validate_runtime_settings_requires_azure_api_key_by_default(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  api_key_env: FSQ_AGENT_MISSING_KEY
""",
        ),
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError, match="API key"):
        validate_runtime_settings(settings)


def test_validate_strict_core_settings_does_not_require_openai_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  api_key_env: FSQ_AGENT_MISSING_KEY
""",
        ),
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    validate_strict_core_settings(settings)


def test_load_settings_accepts_deprecated_shell_without_runtime_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
shell:
  enabled: true
  mode: allowlist
  command_allowlist: []
""",
        ),
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    validate_runtime_settings(settings)
    assert settings.shell.enabled is True
    assert settings.shell.mode == "allowlist"


def test_deprecated_shell_working_dir_is_not_resolved_or_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
shell:
  enabled: true
  mode: allow_all
  command_allowlist: []
  working_dir: .
""",
        ),
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    validate_runtime_settings(settings)
    assert settings.shell.working_dir == "."


def test_load_settings_loads_dotenv_from_config_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  api_key_env: AZURE_OPENAI_API_KEY
""",
        ),
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
        _base_config(
            tmp_path,
            """
openai_agents:
  api_key_env: AZURE_OPENAI_API_KEY
""",
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text("AZURE_OPENAI_API_KEY=from-dotenv\n", encoding="utf-8")

    load_settings(config_path)

    assert __import__("os").environ["AZURE_OPENAI_API_KEY"] == "from-process"


def test_load_settings_rejects_invalid_dotenv_line(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(_base_config(tmp_path), encoding="utf-8")
    (tmp_path / ".env").write_text("not-a-key-value-line\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Invalid .env line"):
        load_settings(config_path)


def test_validate_runtime_settings_rejects_placeholder_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FSQ_AGENT_PLACEHOLDER_KEY", raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        _base_config(
            tmp_path,
            """
openai_agents:
  api_key_env: FSQ_AGENT_PLACEHOLDER_KEY
""",
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "FSQ_AGENT_PLACEHOLDER_KEY=replace-with-your-azure-openai-api-key\n",
        encoding="utf-8",
    )
    settings = load_settings(config_path)

    with pytest.raises(ConfigurationError, match="placeholder"):
        validate_runtime_settings(settings)