import asyncio
import re
from pathlib import Path
from typing import Any

import pytest

from fsq_agent import FsqAgent, Task
from fsq_agent.agent import Verifier
from fsq_agent.agent._openai_runtime import OpenAIAgentsRuntime, _RecentToolOutputInputFilter
from fsq_agent.config import Settings
from fsq_agent.models import ConfigurationError, GoalPrePlan, KnowledgeBundle, ReportArtifact, RunEvent, StepResult
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


class _CancelledRuntime:
    async def run_task(
        self,
        task: Task,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
    ) -> list[StepResult]:
        raise asyncio.CancelledError()


class _PrePlanRuntime:
    def __init__(self) -> None:
        self.loaded_knowledge: KnowledgeBundle | None = None

    async def run_pre_plan(
        self,
        goal: str,
        knowledge: KnowledgeBundle,
        skills: list[object],
        run_id: str,
        event_sink: object | None = None,
    ) -> GoalPrePlan:
        self.loaded_knowledge = knowledge
        return GoalPrePlan(
            goal=goal,
            summary="Generated a plan.",
            relevant_page_ids=["edge_android_new_tab_page"],
            key_actions=[
                {
                    "step_id": 1,
                    "action": "Verify the New Tab Page.",
                    "source_page_ids": ["edge_android_new_tab_page"],
                    "notes": "Use page identifiers.",
                }
            ],
        )


class _FakeArtifactStore:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str, dict[str, Any]]] = []

    def write(self, tool_name: str, output_text: str, metadata: dict[str, Any]) -> Path:
        self.writes.append((tool_name, output_text, metadata))
        return Path("artifact.json")


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


def test_recent_tool_output_filter_does_not_artifact_sensitive_outputs() -> None:
    artifact_store = _FakeArtifactStore()
    input_filter = _RecentToolOutputInputFilter(
        sdk_filter=None,
        recent_tool_outputs=0,
        max_output_chars=1,
        preview_chars=1,
        trimmable_tools=None,
        artifact_store=artifact_store,  # type: ignore[arg-type]
    )

    path = input_filter._artifact_path_for(
        {"call_id": "call-1"},
        {"get_runtime_secret"},
        '{"type":"runtime_secret","name":"TEST_ACCOUNT_PASSWORD","value":"secret","sensitive":true}',
    )

    assert path is None
    assert artifact_store.writes == []


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


@pytest.mark.asyncio
async def test_agent_run_persists_run_failed_for_cancellation(tmp_path: Path) -> None:
    events: list[RunEvent] = []
    agent = FsqAgent(
        Settings(),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        flow_manager=_FlowManager(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=_CancelledRuntime(),  # type: ignore[arg-type]
        event_logger=ExecutionLogger(tmp_path),
    )
    task = Task(id="smoke", name="Smoke", description="Record a smoke test task.")

    with pytest.raises(asyncio.CancelledError):
        await agent.run(task, event_sink=events.append)

    assert [event.type for event in events] == ["run_started", "agent_started", "run_failed"]
    assert events[-1].message == "CancelledError"
    assert events[-1].payload["exception_type"] == "CancelledError"
    timeline_paths = list(tmp_path.glob("smoke-*/events.jsonl"))
    assert len(timeline_paths) == 1
    timeline = timeline_paths[0].read_text(encoding="utf-8")
    assert "run_failed" in timeline
    assert "CancelledError" in timeline


@pytest.mark.asyncio
async def test_agent_pre_plan_goal_loads_index_only_before_runtime_loop(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    pages_dir = knowledge_dir / "pages"
    pages_dir.mkdir(parents=True)
    (knowledge_dir / "index.md").write_text("# Knowledge Index", encoding="utf-8")
    (pages_dir / "edge_android_new_tab_page.md").write_text("# New Tab Page", encoding="utf-8")
    runtime = _PrePlanRuntime()
    events: list[RunEvent] = []
    agent = FsqAgent(
        Settings(knowledge_dir=knowledge_dir),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        flow_manager=_FlowManager(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=runtime,  # type: ignore[arg-type]
    )

    plan = await agent.pre_plan_goal("Open downloads", event_sink=events.append)

    assert plan.goal == "Open downloads"
    assert plan.key_actions[0].action == "Verify the New Tab Page."
    assert runtime.loaded_knowledge is not None
    assert sorted(runtime.loaded_knowledge.items) == ["index.md"]
    assert [event.type for event in events] == ["run_started", "agent_started", "run_completed"]


@pytest.mark.asyncio
async def test_agent_pre_plan_goal_uses_pre_plan_knowledge_dir(tmp_path: Path) -> None:
    private_knowledge_dir = tmp_path / "knowledge"
    page_knowledge_dir = tmp_path / "knowledge" / "project_android_v1"
    private_knowledge_dir.mkdir(parents=True)
    page_knowledge_dir.mkdir(parents=True)
    (private_knowledge_dir / "index.md").write_text("# Private Index", encoding="utf-8")
    (page_knowledge_dir / "index.md").write_text("# Page Graph Index", encoding="utf-8")
    runtime = _PrePlanRuntime()
    agent = FsqAgent(
        Settings(knowledge_dir=private_knowledge_dir, pre_plan={"knowledge_dir": page_knowledge_dir}),
        verifier=Verifier(),
        reporter=_Reporter(),  # type: ignore[arg-type]
        knowledge_loader=_KnowledgeLoader(),  # type: ignore[arg-type]
        flow_manager=_FlowManager(),  # type: ignore[arg-type]
        skill_loader=_SkillLoader(),  # type: ignore[arg-type]
        runtime=runtime,  # type: ignore[arg-type]
    )

    await agent.pre_plan_goal("Open downloads")

    assert runtime.loaded_knowledge is not None
    assert runtime.loaded_knowledge.items["index.md"] == "# Page Graph Index"


@pytest.mark.asyncio
async def test_pre_plan_runtime_reads_page_by_index_page_id(tmp_path: Path) -> None:
    knowledge_dir = tmp_path / "knowledge"
    pages_dir = knowledge_dir / "pages"
    pages_dir.mkdir(parents=True)
    (knowledge_dir / "index.md").write_text(
    """
# Knowledge Index

```json
{
    "schema_version": "page_knowledge_index_v1",
    "product": "Microsoft Edge",
    "platform": "Android",
    "pages": [
        {
            "page_id": "edge_android_new_tab_page",
            "file": "pages/edge_android_new_tab_page.md",
            "name": "New Tab Page",
            "intents": ["new tab"]
        }
    ]
}
```
""",
        encoding="utf-8",
    )
    (pages_dir / "edge_android_new_tab_page.md").write_text("# New Tab Page", encoding="utf-8")
    runtime = OpenAIAgentsRuntime(Settings(knowledge_dir=knowledge_dir), object(), object())  # type: ignore[arg-type]

    output = await runtime._read_knowledge_page_tool(None, '{"page_id":"edge_android_new_tab_page"}')

    assert '"ok": true' in output
    assert "# New Tab Page" in output
    assert "pages/edge_android_new_tab_page.md" in output


@pytest.mark.asyncio
async def test_pre_plan_runtime_reads_from_pre_plan_knowledge_dir(tmp_path: Path) -> None:
    private_knowledge_dir = tmp_path / "knowledge"
    page_knowledge_dir = tmp_path / "knowledge" / "project_android_v1"
    private_knowledge_dir.mkdir(parents=True)
    pages_dir = page_knowledge_dir / "pages"
    pages_dir.mkdir(parents=True)
    (page_knowledge_dir / "index.md").write_text("# Page Graph Index", encoding="utf-8")
    (pages_dir / "edge_android_new_tab_page.md").write_text("# New Tab Page", encoding="utf-8")
    runtime = OpenAIAgentsRuntime(
        Settings(knowledge_dir=private_knowledge_dir, pre_plan={"knowledge_dir": page_knowledge_dir}),
        object(),
        object(),
    )  # type: ignore[arg-type]

    index_output = await runtime._read_knowledge_index_tool(None, "{}")
    page_output = await runtime._read_knowledge_page_tool(None, '{"file":"pages/edge_android_new_tab_page.md"}')

    assert "# Page Graph Index" in index_output
    assert "# New Tab Page" in page_output
