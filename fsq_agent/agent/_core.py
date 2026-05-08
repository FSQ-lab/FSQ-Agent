import time
import uuid
from pathlib import Path

from fsq_agent.config import Settings, load_settings
from fsq_agent.knowledge import FlowTemplateManager, PrivateKnowledgeLoader
from fsq_agent.models import Task, TaskResult
from fsq_agent.report import ReportGenerator
from fsq_agent.skills import SkillLoader
from fsq_agent.tools import AgentsMCPFactory, AgentsToolFactory, CLIRunner, FileOps

from fsq_agent.agent._openai_runtime import OpenAIAgentsRuntime
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
    ) -> None:
        self.settings = settings
        self.verifier = verifier
        self.reporter = reporter
        self.knowledge_loader = knowledge_loader
        self.flow_manager = flow_manager
        self.skill_loader = skill_loader
        self.runtime = runtime

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
        return cls(
            settings,
            Verifier(),
            reporter,
            knowledge_loader,
            flow_manager,
            skill_loader,
            OpenAIAgentsRuntime(settings, tool_factory, mcp_factory),
        )

    async def run(self, task: Task) -> TaskResult:
        started = time.perf_counter()
        run_id = f"{task.id}-{uuid.uuid4().hex[:8]}"
        knowledge = self.knowledge_loader.load_for_task(task)
        knowledge.flow_templates = self.flow_manager.match(task.description)
        skills = self.skill_loader.load(self.settings.skills)
        results = await self.runtime.run_task(task, knowledge, skills)
        verification = await self.verifier.verify(task, results)
        report = self.reporter.generate(run_id, task, results, verification)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return TaskResult(
            task_id=task.id,
            status=verification.status,
            steps=results,
            verification=verification,
            report=report,
            duration_ms=duration_ms,
        )