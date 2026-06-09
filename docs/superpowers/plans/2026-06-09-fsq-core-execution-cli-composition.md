# FSQ Core Execution CLI Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small CLI-layer composition helper that runs one FSQ case through the deterministic core runner with a caller-supplied harness and writes the evidence manifest.

**Architecture:** Keep `core` and `fsq` independent per `CLAUDE.md`: `fsq` loads and adapts YAML into shared `ExecutableStep` models, `core` executes those models, and `cli` composes both at the entry boundary. The helper is internal for now and returns the existing `EvidenceBundle` with `manifest_path` populated after writing `evidence-manifest.json`.

**Tech Stack:** Python, Pydantic models, pytest, existing `FsqCaseLoader`, `FsqExecutableStepAdapter`, `StepSequenceRunner`, and `EvidenceRecorder`.

---

### File Structure

- Modify: `CLAUDE.md` to document that CLI may depend on `core` as the entry layer that composes FSQ and core execution.
- Modify: `fsq_agent/cli/SPEC.md` to specify the internal deterministic core execution helper and keep existing user-facing commands unchanged.
- Create: `fsq_agent/cli/_core_execution.py` for FSQ-case-to-core-runner composition.
- Test: `tests/test_cli_core_execution.py` for the new helper.

### Task 1: Document The Entry-Layer Composition Contract

**Files:**
- Modify: `CLAUDE.md`
- Modify: `fsq_agent/cli/SPEC.md`

- [x] **Step 1: Update architecture documentation**

Add `Core` as a dependency of `CLI` in the architecture diagram and list. This documents that CLI may compose `fsq` and `core`, while `core` and `fsq` remain independent.

- [x] **Step 2: Update CLI SPEC**

Add an internal helper contract:

```python
bundle = run_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
)
```

The helper loads the FSQ case, adapts commands to `ExecutableStep`, runs `StepSequenceRunner`, writes `evidence-manifest.json`, and returns an `EvidenceBundle` whose `manifest_path` points to the written manifest.

### Task 2: Add Failing Helper Test

**Files:**
- Create: `tests/test_cli_core_execution.py`

- [x] **Step 1: Write the failing test**

Create a minimal harness and FSQ case. Assert the helper writes a manifest and returns a bundle with step results and manifest path.

```python
def test_run_fsq_core_case_writes_manifest_and_returns_bundle(tmp_path: Path) -> None:
    case_path = tmp_path / "core_cli.codex.yaml"
    case_path.write_text(FSQ_CASE, encoding="utf-8")

    bundle = run_fsq_core_case(
        case_path=case_path,
        harness=CliCoreHarness(),
        output_dir=tmp_path / "runs" / "run-1",
        run_id="run-1",
    )

    assert bundle.run_id == "run-1"
    assert bundle.manifest_path == tmp_path / "runs" / "run-1" / "evidence-manifest.json"
    assert bundle.manifest_path.exists()
    assert [step.step_id for step in bundle.steps] == ["core_cli-step-001", "core_cli-step-002"]
```

- [x] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_cli_core_execution.py -q`

Expected: FAIL with an import error because `fsq_agent.cli._core_execution` does not exist yet.

### Task 3: Implement Minimal Composition Helper

**Files:**
- Create: `fsq_agent/cli/_core_execution.py`

- [x] **Step 1: Add implementation**

Implement:

```python
from pathlib import Path

from fsq_agent.core import EvidenceRecorder, HarnessInterface, StepSequenceRunner
from fsq_agent.fsq import FsqCaseLoader, FsqExecutableStepAdapter
from fsq_agent.models import EvidenceBundle


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
```

- [x] **Step 2: Run the narrow test**

Run: `pytest tests/test_cli_core_execution.py -q`

Expected: PASS.

### Task 4: Verify And Commit

**Files:**
- Modified files from Tasks 1-3.

- [x] **Step 1: Run related tests**

Run: `pytest tests/test_cli_core_execution.py tests/test_fsq_evidence_manifest_smoke.py tests/test_cli.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run: `pytest -q`

Expected: PASS.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 3: Commit**

Run:

```bash
git add CLAUDE.md fsq_agent/cli/SPEC.md fsq_agent/cli/_core_execution.py tests/test_cli_core_execution.py docs/superpowers/plans/2026-06-09-fsq-core-execution-cli-composition.md
git commit -m "feat: add fsq core execution composition"
```

### Self-Review

- Spec coverage: The plan documents the new entry-layer dependency and internal helper contract before implementation.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: The helper uses existing `HarnessInterface` and returns existing `EvidenceBundle`.
