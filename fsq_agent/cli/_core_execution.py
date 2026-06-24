from pathlib import Path

from fsq_agent.cli._capability_bootstrap import build_capability_executor_bindings, build_capability_registry
from fsq_agent.core import CapabilityExecutorBindings, CapabilityRegistry, EvidenceRecorder, HarnessInterface, StepRunner, StepSequenceRunner
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import EvidenceBundle, ExecutableStep, ReportArtifact, ReportGenerationError
from fsq_agent.report import CoreEvidenceReportGenerator


def run_fsq_core_case(
    *,
    case_path: str | Path,
    harness: HarnessInterface,
    output_dir: str | Path,
    run_id: str,
    registry: CapabilityRegistry | None = None,
    executors: CapabilityExecutorBindings | None = None,
    steps: list[ExecutableStep] | None = None,
    step_interval_seconds: float = 1.0,
) -> EvidenceBundle:
    registry = registry or build_capability_registry()
    executors = executors or build_capability_executor_bindings()
    if steps is None:
        case = FsqCaseLoader().load_case(Path(case_path))
        steps = FsqExecutableStepAdapter(registry_snapshot=registry.snapshot()).to_executable_steps(case)
    normal_steps, teardown_steps = _split_trailing_teardown_steps(steps)
    recorder = EvidenceRecorder(run_id=run_id, output_dir=Path(output_dir))
    bundle = StepSequenceRunner(
        step_runner=StepRunner(harness=harness, capability_registry=registry, executor_bindings=executors),
        evidence_recorder=recorder,
        step_interval_seconds=step_interval_seconds,
    ).run_steps(
        run_id=run_id,
        steps=normal_steps,
        teardown_steps=teardown_steps,
    )
    manifest_path = recorder.write_manifest()
    return bundle.model_copy(update={"manifest_path": manifest_path})


def _split_trailing_teardown_steps(steps: list[ExecutableStep]) -> tuple[list[ExecutableStep], list[ExecutableStep]]:
    split_at = len(steps)
    while split_at > 0 and steps[split_at - 1].kind == "teardown":
        split_at -= 1
    return steps[:split_at], steps[split_at:]


def run_strict_fsq_core_case(
    *,
    case_path: str | Path,
    harness: HarnessInterface,
    output_dir: str | Path,
    run_id: str,
    registry: CapabilityRegistry | None = None,
    executors: CapabilityExecutorBindings | None = None,
    steps: list[ExecutableStep] | None = None,
    step_interval_seconds: float = 1.0,
) -> ReportArtifact:
    bundle = run_fsq_core_case(
        case_path=case_path,
        harness=harness,
        output_dir=output_dir,
        run_id=run_id,
        registry=registry,
        executors=executors,
        steps=steps,
        step_interval_seconds=step_interval_seconds,
    )
    if bundle.manifest_path is None:
        raise ReportGenerationError(
            "Strict core run did not produce an evidence manifest.",
            context={"run_id": run_id},
        )
    return CoreEvidenceReportGenerator().generate_from_manifest(bundle.manifest_path)
