from pathlib import Path

from fsq_agent.core import EvidenceRecorder, HarnessInterface, StepSequenceRunner
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import EvidenceBundle, ReportArtifact, ReportGenerationError
from fsq_agent.report import CoreEvidenceReportGenerator


def run_fsq_core_case(
    *,
    case_path: str | Path,
    harness: HarnessInterface,
    output_dir: str | Path,
    run_id: str,
) -> EvidenceBundle:
    case = FsqCaseLoader().load_case(Path(case_path))
    steps = FsqExecutableStepAdapter().to_executable_steps(case)
    recorder = EvidenceRecorder(run_id=run_id, output_dir=Path(output_dir))
    bundle = StepSequenceRunner(harness=harness, evidence_recorder=recorder).run_steps(run_id=run_id, steps=steps)
    manifest_path = recorder.write_manifest()
    return bundle.model_copy(update={"manifest_path": manifest_path})


def run_strict_fsq_core_case(
    *,
    case_path: str | Path,
    harness: HarnessInterface,
    output_dir: str | Path,
    run_id: str,
) -> ReportArtifact:
    bundle = run_fsq_core_case(
        case_path=case_path,
        harness=harness,
        output_dir=output_dir,
        run_id=run_id,
    )
    if bundle.manifest_path is None:
        raise ReportGenerationError(
            "Strict core run did not produce an evidence manifest.",
            context={"run_id": run_id},
        )
    return CoreEvidenceReportGenerator().generate_from_manifest(bundle.manifest_path)
