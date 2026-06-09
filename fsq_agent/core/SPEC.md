# Module: core

## Purpose

Define the shared execution-core orchestration layer for FSQ-Agent. The core module owns the StepRunner protocol boundary, harness capability interface, and evidence-recording coordination points that will let FSQ YAML execution and natural-goal execution converge before platform operations.

The module is contract-first. Implementation must not start until this SPEC and the corresponding shared model changes in `fsq_agent/models/SPEC.md` are reviewed and confirmed.

## Dependencies

- `models`: Uses shared execution-core data structures such as executable steps, phase reports, runner events, harness context/results, artifact refs, evidence bundle manifests, and execution failure/status literals.

The core module must not depend on `agent`, `cli`, `fsq`, `report`, `observation`, `knowledge`, `skills`, or concrete platform tool modules in its first contract batch.

## Public Interface

Planned `__init__.py` exports via `__all__`:

- `HarnessInterface`: Protocol describing platform capabilities required by StepRunner. Concrete Android, Web, iOS, and fake harnesses may satisfy the protocol structurally.
- `StepRunner`: Minimal synchronous runner that executes one `ExecutableStep` through the `prepare`, `invoke`, and `finalize` phases using a supplied `HarnessInterface`.

Planned subpackage exports:

- `fsq_agent.core.runner`: Home for `StepRunner` and runner orchestration helpers. It imports shared runner models from `fsq_agent.models` rather than defining cross-module data models locally.
- `fsq_agent.core.harness`: Home for `HarnessInterface` and future harness-neutral helper code. It imports shared harness models from `fsq_agent.models`.
- `fsq_agent.core.evidence`: Future home for `EvidenceRecorder` and evidence coordination logic. It imports evidence bundle and artifact models from `fsq_agent.models`.

The first runner implementation exposes a narrow synchronous API:

```python
runner = StepRunner(harness=harness)
result = runner.run_step(run_id="run-1", step=executable_step)
events = runner.events
```

`StepRunner` accepts any object satisfying `HarnessInterface`. Entry-layer code and future factories are responsible for constructing platform-specific harnesses such as Android, Web, iOS, or fake harnesses.

## Internal Structure

Planned structure after the first implementation batch:

- `__init__.py`: Public exports only.
- `runner/__init__.py`: Runner subpackage exports only.
- `runner/_runner.py`: `StepRunner` implementation for the minimal single-step protocol.
- `harness/__init__.py`: Harness subpackage exports only.
- `harness/_interface.py`: `HarnessInterface` protocol.
- `evidence/__init__.py`: Evidence subpackage exports only.
- `evidence/_recorder.py`: Future `EvidenceRecorder` implementation.
- `SPEC.md`: Module design.

The core module must not define Pydantic models that are shared across modules. Shared models belong in `fsq_agent.models` according to the project guide.

## Error Handling

Core orchestration code should convert phase-level exceptions into shared structured result models owned by `models`. It should not introduce custom exceptions in this module. Any new project-wide exception class must be defined in `fsq_agent.models` and documented in `fsq_agent/models/SPEC.md` first.

Runner phases should preserve failure boundaries:

- prepare failures: context, setup, validation, or before-action observation failures
- invoke failures: action, target, timeout, platform command, or assertion failures
- finalize failures: after-action observation, artifact capture, stabilization, or cleanup failures

## Design Decisions

- `core` owns execution control boundaries, not shared data models.
- `models` owns serializable execution contracts, result records, runner events, harness context/result records, evidence manifests, and status/failure taxonomies.
- `HarnessInterface` is a protocol because it represents platform capability rather than persisted data.
- `StepRunner` should call harness capabilities through `HarnessInterface`, emit shared runner events, and return shared step result models.
- The minimal runner slice is synchronous. Async support should be decided when real MCP/Appium/Playwright harness integration is planned.
- Fake harnesses for the minimal runner slice should live in tests until a reusable product fake is needed.
- `EvidenceRecorder` should consume shared runner events and result facts. It should not execute actions, retry steps, or decide case success.
- Concrete Android/Web/iOS harness implementations are out of scope for the first contract batch and must not be placed in `core`.
- CLI, report generation, verifier behavior, planner repair, and FSQ StepBuilder integration are later batches.
