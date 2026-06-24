from pathlib import Path

import pytest

from fsq_agent._capability_bootstrap import build_capability_registry
from fsq_agent.cli._strict_replay import collect_runtime_secret_refs, resolve_strict_replay_steps
from fsq_agent.config._settings import Settings
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import ConfigurationError, RuntimeSecretSettings


def _secret_case_steps(tmp_path: Path):
    case_path = tmp_path / "secret.codex.yaml"
    case_path.write_text(
        """
schemaVersion: fsq.ai-test/v1
name: Secret Replay
platform: android
---
- inputText:
    text:
      runtimeSecret: TEST_ACCOUNT_PASSWORD
    target: Password field
""",
        encoding="utf-8",
    )
    return FsqExecutableStepAdapter(registry_snapshot=build_capability_registry().snapshot()).to_executable_steps(
        FsqCaseLoader().load_case(case_path)
    )


def test_resolve_strict_replay_steps_substitutes_runtime_secret_in_memory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TEST_ACCOUNT_PASSWORD", "super-secret")
    settings = Settings(runtime_secrets=RuntimeSecretSettings(allowed_env_names=["TEST_ACCOUNT_PASSWORD"]))
    steps = _secret_case_steps(tmp_path)

    resolved = resolve_strict_replay_steps(steps, settings)

    assert collect_runtime_secret_refs(steps[0].params) == {"TEST_ACCOUNT_PASSWORD"}
    assert resolved[0].params["text"] == "super-secret"
    assert steps[0].params["text"] == {"runtimeSecret": "TEST_ACCOUNT_PASSWORD"}


def test_resolve_strict_replay_steps_requires_allowlisted_secret(tmp_path: Path) -> None:
    steps = _secret_case_steps(tmp_path)

    with pytest.raises(ConfigurationError, match="not allowed"):
        resolve_strict_replay_steps(steps, Settings())