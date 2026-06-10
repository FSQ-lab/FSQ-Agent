# Step Runner Core Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first contract-only batch for FSQ-Agent's StepRunner core: shared models in `models`, harness protocol in `core`, explicit exports, and focused tests.

**Architecture:** Shared serializable contracts live in `fsq_agent.models` per `CLAUDE.md`. `fsq_agent.core` owns execution orchestration boundaries and defines `HarnessInterface` as a protocol that consumes model-owned contracts. No real runner, real harness, CLI integration, report integration, or verifier integration is implemented in this batch.

**Tech Stack:** Python, Pydantic, `typing.Protocol`, pytest.

---

## File Structure

- Create `fsq_agent/models/_core.py`: execution-core Pydantic models, literal type aliases, and JSON-serializable validation helpers.
- Modify `fsq_agent/models/__init__.py`: export the new shared contracts through explicit `__all__`.
- Create `fsq_agent/core/__init__.py`: export core public protocol symbols.
- Create `fsq_agent/core/harness/__init__.py`: export harness public protocol symbols.
- Create `fsq_agent/core/harness/_interface.py`: define `HarnessInterface` as a runtime-checkable `Protocol`.
- Create `fsq_agent/core/runner/__init__.py`: placeholder subpackage exports for future runner implementation.
- Create `fsq_agent/core/evidence/__init__.py`: placeholder subpackage exports for future evidence implementation.
- Create `tests/test_core_contracts.py`: contract tests for models, protocol conformance, serialization, and exports.

### Task 1: Model Contracts

**Files:**
- Create: `fsq_agent/models/_core.py`
- Modify: `fsq_agent/models/__init__.py`
- Test: `tests/test_core_contracts.py`

- [x] **Step 1: Write failing model contract tests**

Add `tests/test_core_contracts.py` with tests that import the planned model names, instantiate an `ExecutableStep`, validate invalid literals, and serialize an `EvidenceBundle`.

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from fsq_agent.models import (
    EvidenceArtifactRef,
    EvidenceBundle,
    EvidencePolicy,
    ExecutableStep,
    HarnessActionResult,
    HarnessArtifactRef,
    HarnessContext,
    RetryPolicy,
    RunnerEvent,
    RunnerStepResult,
    SourceRef,
    StepCallInfo,
    StepPhaseReport,
)


def test_executable_step_accepts_contract_fields() -> None:
    step = ExecutableStep(
        step_id="step-1",
        source_ref=SourceRef(source_type="fsq", source_id="case.yaml", step_index=1),
        kind="action",
        action_name="tap",
        params={"text": "Login"},
        target_ref="button:login",
        retry_policy=RetryPolicy(max_attempts=2),
        evidence_policy=EvidencePolicy(capture_before=True, capture_after=True),
        timeout_ms=5000,
        metadata={"owner": "test"},
    )

    assert step.step_id == "step-1"
    assert step.kind == "action"
    assert step.retry_policy.max_attempts == 2
    assert step.evidence_policy.capture_after is True


def test_executable_step_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        ExecutableStep(step_id="step-1", kind="unknown", action_name="tap")


def test_phase_report_preserves_phase_failure_boundary() -> None:
    report = StepPhaseReport(
        step_id="step-1",
        phase="prepare",
        status="failed",
        duration_ms=12,
        failure_category="context_error",
        error_message="context unavailable",
    )

    assert report.phase == "prepare"
    assert report.failure_category == "context_error"


def test_runner_event_requires_known_event_type() -> None:
    with pytest.raises(ValidationError):
        RunnerEvent(run_id="run-1", event_type="unknown", payload={})


def test_evidence_bundle_serializes_artifact_refs_without_binary_payloads() -> None:
    created_at = datetime.now(timezone.utc)
    artifact = EvidenceArtifactRef(
        artifact_id="artifact-1",
        kind="screenshot",
        path=Path("runs/run-1/screenshot.png"),
        mime_type="image/png",
        created_at=created_at,
        step_id="step-1",
        phase="finalize",
    )
    bundle = EvidenceBundle(
        bundle_id="bundle-1",
        run_id="run-1",
        created_at=created_at,
        manifest_path=Path("runs/run-1/evidence.json"),
        artifacts=[artifact],
    )

    payload = bundle.model_dump(mode="json")

    assert payload["artifacts"][0]["path"] == "runs/run-1/screenshot.png"
    assert "bytes" not in payload["artifacts"][0]


def test_runner_step_result_uses_distinct_name_from_legacy_step_result() -> None:
    result = RunnerStepResult(
        step_id="step-1",
        status="passed",
        phase_reports=[StepPhaseReport(step_id="step-1", phase="invoke", status="passed")],
    )

    assert result.status == "passed"
    assert result.phase_reports[0].phase == "invoke"


def test_harness_models_capture_context_action_and_artifacts() -> None:
    artifact = HarnessArtifactRef(artifact_id="artifact-1", kind="log", path=Path("runs/run-1/action.log"))
    context = HarnessContext(platform="android", session_id="session-1", current_activity="MainActivity")
    result = HarnessActionResult(status="passed", action_name="tap", artifact_refs=[artifact])

    assert context.platform == "android"
    assert result.artifact_refs[0].kind == "log"
```

- [x] **Step 2: Run model tests to verify they fail**

Run: `pytest tests/test_core_contracts.py -q`

Expected: FAIL during import because the new core contract models are not exported yet.

- [x] **Step 3: Implement model contracts**

Create `fsq_agent/models/_core.py` with Pydantic models and type aliases matching the tests.

- [x] **Step 4: Export model contracts**

Modify `fsq_agent/models/__init__.py` to import all new names from `_core.py` and include them in `__all__`.

- [x] **Step 5: Run model tests to verify they pass**

Run: `pytest tests/test_core_contracts.py -q`

Expected: PASS.

### Task 2: Harness Protocol And Core Exports

**Files:**
- Create: `fsq_agent/core/__init__.py`
- Create: `fsq_agent/core/harness/__init__.py`
- Create: `fsq_agent/core/harness/_interface.py`
- Create: `fsq_agent/core/runner/__init__.py`
- Create: `fsq_agent/core/evidence/__init__.py`
- Modify: `tests/test_core_contracts.py`

- [x] **Step 1: Write failing harness protocol tests**

Append tests that import `HarnessInterface`, define a lightweight fake harness, and assert runtime protocol conformance plus explicit exports.

- [x] **Step 2: Run protocol tests to verify they fail**

Run: `pytest tests/test_core_contracts.py -q`

Expected: FAIL because `fsq_agent.core` and `HarnessInterface` exports are not implemented yet.

- [x] **Step 3: Implement `HarnessInterface` protocol and package exports**

Create the core package files. `HarnessInterface` should be `@runtime_checkable` and define `get_context`, `action_space`, `before_action`, `invoke_action`, `after_action`, `capture_artifact`, and `classify_error` with model-owned input/output types.

- [x] **Step 4: Run protocol tests to verify they pass**

Run: `pytest tests/test_core_contracts.py -q`

Expected: PASS.

### Task 3: Repository Verification

**Files:**
- Verify: touched code and tests

- [x] **Step 1: Run focused contract tests**

Run: `pytest tests/test_core_contracts.py -q`

Expected: PASS.

- [x] **Step 2: Run existing model tests**

Run: `pytest tests/test_models.py -q`

Expected: PASS.

- [x] **Step 3: Run full test suite**

Run: `pytest -q`

Expected: PASS or report exact pre-existing failures if unrelated.

- [x] **Step 4: Review diff for scope and project-guide compliance**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors; only intended files modified plus the user's untracked `docs/step-runner-architecture.md` remaining untouched.

- [ ] **Step 5: Commit implementation**

Run: `git add fsq_agent/models/_core.py fsq_agent/models/__init__.py fsq_agent/core/__init__.py fsq_agent/core/harness/__init__.py fsq_agent/core/harness/_interface.py fsq_agent/core/runner/__init__.py fsq_agent/core/evidence/__init__.py tests/test_core_contracts.py docs/superpowers/plans/2026-06-09-step-runner-core-contracts.md && git commit -m "feat: add step runner core contracts"`
