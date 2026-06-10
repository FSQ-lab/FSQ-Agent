from collections.abc import Sequence

from fsq_agent.core.evidence import EvidenceRecorder
from fsq_agent.core.harness import HarnessInterface
from fsq_agent.core.runner._runner import StepRunner
from fsq_agent.models import EvidenceBundle, ExecutableStep


_STOP_STATUSES = {"failed", "cancelled", "skipped"}


class _StepSequenceFailure(Exception):
    pass


class StepSequenceRunner:
    def __init__(self, harness: HarnessInterface, evidence_recorder: EvidenceRecorder) -> None:
        self.harness = harness
        self.evidence_recorder = evidence_recorder

    def run_steps(
        self,
        run_id: str,
        steps: Sequence[ExecutableStep],
        teardown_steps: Sequence[ExecutableStep] = (),
    ) -> EvidenceBundle:
        try:
            for step in steps:
                result = self._run_and_record(run_id, step)
                if result.status in _STOP_STATUSES:
                    raise _StepSequenceFailure
        except _StepSequenceFailure:
            pass
        finally:
            for step in teardown_steps:
                self._run_and_record(run_id, step)
        return self.evidence_recorder.build_bundle()

    def _run_and_record(self, run_id: str, step: ExecutableStep):
        step_runner = StepRunner(harness=self.harness)
        result = step_runner.run_step(run_id=run_id, step=step)
        for event in step_runner.events:
            self.evidence_recorder.record_event(event)
        self.evidence_recorder.record_step_result(result)
        return result
