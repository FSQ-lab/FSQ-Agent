import time
from datetime import datetime
from pathlib import Path

from fsq_agent.config import Settings, load_settings
from fsq_agent.knowledge import PrivateKnowledgeLoader
from fsq_agent.models import GoalPrePlan, KnowledgeBundle, RunEvent, RunEventSink, Task, TaskResult
from fsq_agent.observation import ExecutionLogger
from fsq_agent.report import ReportGenerator
from fsq_agent.skills import SkillLoader
from fsq_agent.tools import AgentsMCPFactory, AgentsToolFactory, CLIRunner, FileOps

from fsq_agent.agent._openai_runtime import OpenAIAgentsRuntime
from fsq_agent.agent._events import RunEventEmitter
from fsq_agent.agent._verifier import Verifier


class FsqAgent:
    def __init__(
        self,
        settings: Settings,
        verifier: Verifier,
        reporter: ReportGenerator,
        knowledge_loader: PrivateKnowledgeLoader,
        skill_loader: SkillLoader,
        runtime: OpenAIAgentsRuntime,
        event_logger: ExecutionLogger | None = None,
    ) -> None:
        self.settings = settings
        self.verifier = verifier
        self.reporter = reporter
        self.knowledge_loader = knowledge_loader
        self.skill_loader = skill_loader
        self.runtime = runtime
        self.event_logger = event_logger

    @classmethod
    def from_config(cls, path: str | Path | None = None, workspace: str | Path | None = None) -> "FsqAgent":
        return cls.from_settings(load_settings(path, workspace))

    @classmethod
    def from_settings(cls, settings: Settings) -> "FsqAgent":
        output_root = settings.output.root_dir
        pre_plan_knowledge_dir = settings.pre_plan.knowledge_dir or settings.knowledge_dir
        cli_runner = CLIRunner(settings.cli_tools, cwd=settings.workspace.root_dir)
        file_ops = FileOps(
            read_roots=[settings.cases.dir, settings.knowledge_dir, pre_plan_knowledge_dir, output_root],
            write_root=output_root / "artifacts",
        )
        tool_factory = AgentsToolFactory(
            cli_runner,
            file_ops,
            settings.shell,
            settings.openai_agents.local_tool_output,
            settings.output.runs_dir,
            settings.runtime_secrets,
        )
        mcp_factory = AgentsMCPFactory(settings.mcp_servers, settings.mcp_tool_validation)
        knowledge_loader = PrivateKnowledgeLoader(settings.knowledge_dir)
        skill_loader = SkillLoader(settings.knowledge_dir / "skills")
        reporter = ReportGenerator(settings.output.runs_dir)
        event_logger = ExecutionLogger(settings.output.runs_dir)
        return cls(
            settings,
            Verifier(),
            reporter,
            knowledge_loader,
            skill_loader,
            OpenAIAgentsRuntime(settings, tool_factory, mcp_factory),
            event_logger,
        )

    async def run(self, task: Task, event_sink: RunEventSink | None = None) -> TaskResult:
        started = time.perf_counter()
        run_id = f"{task.id}-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        emitter = RunEventEmitter(self.event_logger, event_sink)
        await emitter.emit(
            RunEvent(run_id=run_id, task_id=task.id, type="run_started", title="Run started", message=task.name)
        )
        try:
            knowledge = self.knowledge_loader.load_for_task(task)
            skills = self.skill_loader.load(self.settings.skills)
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="agent_started",
                    title="Agent context loaded",
                    message=f"Loaded {len(skills)} skills and {len(knowledge.items)} knowledge items.",
                    payload={"skill_count": len(skills), "knowledge_item_count": len(knowledge.items)},
                )
            )
            results = await self.runtime.run_task(task, knowledge, skills, run_id, emitter.emit)
            events_path = self.event_logger.log_root / run_id / "events.jsonl" if self.event_logger else None
            run_verification_task = getattr(self.runtime, "_run_verification_task", None)
            if callable(run_verification_task):
                results.extend(await run_verification_task(task, results, run_id, events_path, emitter.emit))
            verification = await self.verifier.verify(task, results, events_path=events_path, mode=self.settings.verification.mode)
            report = self.reporter.generate(run_id, task, results, verification)
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = TaskResult(
                task_id=task.id,
                status=verification.status,
                steps=results,
                verification=verification,
                report=report,
                duration_ms=duration_ms,
            )
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="run_completed",
                    title="Run completed",
                    message=verification.summary,
                    duration_ms=duration_ms,
                    payload={"status": verification.status, "report_path": str(report.path)},
                )
            )
            return result
        except BaseException as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            message = str(exc) or exc.__class__.__name__
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="run_failed",
                    title="Run failed",
                    message=message,
                    duration_ms=duration_ms,
                    payload={"exception_type": exc.__class__.__name__},
                )
            )
            raise

    async def pre_plan_goal(self, goal: str, event_sink: RunEventSink | None = None) -> GoalPrePlan:
        run_id = f"pre-plan-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        emitter = RunEventEmitter(self.event_logger, event_sink)
        await emitter.emit(
            RunEvent(run_id=run_id, task_id="pre-plan", type="run_started", title="Pre-plan run started", message=goal)
        )
        try:
            knowledge = self._load_page_knowledge_index()
            skills = self.skill_loader.load(self.settings.skills)
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id="pre-plan",
                    type="agent_started",
                    title="Pre-plan context loaded",
                    message=f"Loaded {len(knowledge.items)} knowledge items and {len(skills)} skills.",
                    payload={"knowledge_item_count": len(knowledge.items), "skill_count": len(skills)},
                )
            )
            pre_plan = await self.runtime.run_pre_plan(goal, knowledge, skills, run_id, emitter.emit)
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id="pre-plan",
                    type="run_completed",
                    title="Pre-plan completed",
                    message=pre_plan.summary or f"Generated {len(pre_plan.key_actions)} key actions.",
                    payload={"key_action_count": len(pre_plan.key_actions), "relevant_page_ids": pre_plan.relevant_page_ids},
                )
            )
            return pre_plan
        except BaseException as exc:
            message = str(exc) or exc.__class__.__name__
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id="pre-plan",
                    type="run_failed",
                    title="Pre-plan run failed",
                    message=message,
                    payload={"exception_type": exc.__class__.__name__},
                )
            )
            raise

    def _load_page_knowledge_index(self) -> KnowledgeBundle:
        items: dict[str, str] = {}
        warnings: list[str] = []
        knowledge_dir = self.settings.pre_plan.knowledge_dir or self.settings.knowledge_dir
        index_path = knowledge_dir / "index.md"
        if index_path.exists():
            items["index.md"] = index_path.read_text(encoding="utf-8")
        else:
            warnings.append("Knowledge index not found: index.md")
        return KnowledgeBundle(items=items, warnings=warnings)
