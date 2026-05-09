import re
from pathlib import Path

import pytest

from fsq_agent import FsqAgent, Task
from fsq_agent.agent import Verifier
from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError, KnowledgeBundle, ReportArtifact, RunEvent, StepResult
from fsq_agent.observation import ExecutionLogger


@pytest.mark.asyncio
async def test_agent_run_requires_openai_agents_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
                """
output:
  root_dir: output
  runs_dir: runs
workspace:
  root_dir: workspace
cases:
  dir: cases
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
        await FsqAgent.from_config(config_path).run(task)


class _KnowledgeLoader:
    def load_for_task(self, task: Task) -> KnowledgeBundle:
        return KnowledgeBundle()


class _FlowManager:
    def match(self, description: str) -> dict[str, object]:
        return {}


class _SkillLoader:
    def load(self, skills: list[object]) -> list[object]:
        return []


class _Runtime:
    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
    ) -> list[StepResult]:
        return [
            StepResult(
                step_id=1,
                status="success",
                actual_outcome='{"status":"success","summary":"Done","pre_plan":[],"plan_updates":[],"satisfied_criteria":["A report exists."],"unmet_criteria":[],"evidence":["Report generated"],"errors":[]}',
                tool_name="openai_agents.runner",
            )
        ]


class _Reporter:
    def __init__(self) -> None:
        self.run_ids: list[str] = []

    def generate(self, run_id: str, task: Task, steps: list[StepResult], verification: object) -> ReportArtifact:
        self.run_ids.append(run_id)
        return ReportArtifact(run_id=run_id, path=Path("report.md"))


@pytest.mark.asyncio
async def test_agent_run_id_uses_friendly_timestamp_suffix() -> None:
    reporter = _Reporter()
    agent = FsqAgent(
        Settings(),
        verifier=Verifier(),
        reporter=reporter,  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        flow_manager=_FlowManager(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=_Runtime(),  # type: ignore[arg-type]
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        acceptance_criteria=["A report exists."],
    )

    result = await agent.run(task)

    assert result.report.run_id == reporter.run_ids[0]
    assert re.fullmatch(r"smoke-\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}", result.report.run_id)


@pytest.mark.asyncio
async def test_agent_run_emits_and_persists_live_events(tmp_path: Path) -> None:
    reporter = _Reporter()
    events: list[RunEvent] = []
    agent = FsqAgent(
        Settings(),
        verifier=Verifier(),
        reporter=reporter,  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        flow_manager=_FlowManager(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=_Runtime(),  # type: ignore[arg-type]
        event_logger=ExecutionLogger(tmp_path),
    )
    task = Task(
        id="smoke",
        name="Smoke",
        description="Record a smoke test task.",
        acceptance_criteria=["A report exists."],
    )

    result = await agent.run(task, event_sink=events.append)

    assert [event.type for event in events] == ["run_started", "agent_started", "run_completed"]
    assert [event.sequence for event in events] == [1, 2, 3]
    timeline_path = tmp_path / result.report.run_id / "events.jsonl"
    assert timeline_path.exists()
    assert "run_completed" in timeline_path.read_text(encoding="utf-8")
