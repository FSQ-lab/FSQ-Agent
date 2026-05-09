import time
from datetime import datetime
from pathlib import Path

from fsq_agent.config import Settings, load_settings
from fsq_agent.knowledge import FlowTemplateManager, PrivateKnowledgeLoader
from fsq_agent.models import RunEvent, RunEventSink, Task, TaskResult
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
        flow_manager: FlowTemplateManager,
        skill_loader: SkillLoader,
        runtime: OpenAIAgentsRuntime,
        event_logger: ExecutionLogger | None = None,
    ) -> None:
        self.settings = settings
        self.verifier = verifier
        self.reporter = reporter
        self.knowledge_loader = knowledge_loader
        self.flow_manager = flow_manager
        self.skill_loader = skill_loader
        self.runtime = runtime
        self.event_logger = event_logger

    @classmethod
    def from_config(cls, path: str | Path | None = None, workspace: str | Path | None = None) -> "FsqAgent":
        return cls.from_settings(load_settings(path, workspace))

    @classmethod
    def from_settings(cls, settings: Settings) -> "FsqAgent":
        output_root = settings.output.root_dir
        cli_runner = CLIRunner(settings.cli_tools, cwd=settings.workspace.root_dir)
        file_ops = FileOps(
            read_roots=[settings.cases.dir, settings.knowledge_dir, output_root],
            write_root=output_root / "artifacts",
        )
        tool_factory = AgentsToolFactory(cli_runner, file_ops, settings.shell)
        mcp_factory = AgentsMCPFactory(settings.mcp_servers, settings.mcp_tool_validation)
        knowledge_loader = PrivateKnowledgeLoader(settings.knowledge_dir)
        flow_manager = FlowTemplateManager(settings.knowledge_dir / "flows")
        skill_loader = SkillLoader(settings.knowledge_dir / "skills")
        reporter = ReportGenerator(settings.output.runs_dir)
        event_logger = ExecutionLogger(settings.output.runs_dir)
        return cls(
            settings,
            Verifier(),
            reporter,
            knowledge_loader,
            flow_manager,
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
            knowledge.flow_templates = self.flow_manager.match(task.description)
            skills = self.skill_loader.load(self.settings.skills)
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="agent_started",
                    title="Agent context loaded",
                    message=f"Loaded {len(skills)} skills and {len(knowledge.flow_templates)} flow templates.",
                    payload={"skill_count": len(skills), "flow_template_count": len(knowledge.flow_templates)},
                )
            )
            results = await self.runtime.run_task(task, knowledge, skills, run_id, emitter.emit)
            verification = await self.verifier.verify(task, results)
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
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            await emitter.emit(
                RunEvent(
                    run_id=run_id,
                    task_id=task.id,
                    type="run_failed",
                    title="Run failed",
                    message=str(exc),
                    duration_ms=duration_ms,
                )
            )
            raise
