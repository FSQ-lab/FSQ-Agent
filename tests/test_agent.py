from pathlib import Path

import pytest

from auto_test_agent import AutoTestAgent, Task
from auto_test_agent.models import ConfigurationError


@pytest.mark.asyncio
async def test_agent_run_requires_openai_agents_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
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
knowledge_dir: knowledge
""",
        encoding="utf-8",
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        acceptance_criteria=["A report exists."],
    )

    with pytest.raises(ConfigurationError, match="OpenAI Agents SDK must be enabled"):
        await AutoTestAgent.from_config(config_path).run(task)