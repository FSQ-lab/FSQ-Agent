# Dynamic Harness Evidence Capture Design

Date: 2026-06-17
Status: Draft for review

## Goal

Make dynamic LLM harness tool calls produce the same kind of before/after UI evidence that operators expect from runner-owned execution. When a dynamic run performs a real UI-changing Android action such as `tapOn`, the run should persist screenshots and UI trees before and after the action.

The immediate motivating case is a dynamic, non-strict Edge run using a raw `.codex.yaml` reference. The dynamic path reaches `HarnessToolAdapter`, but the adapter currently calls `harness.get_context()` and `harness.invoke_action()` directly. That bypasses `StepRunner`, so `prepare` and `finalize` evidence capture hooks do not run.

## Scope

This design covers dynamic harness action execution owned by `agent`:

- `fsq-agent run --goal ...`
- `fsq-agent run --case-yaml ...`
- `fsq-agent run --case-dir ...`

The implementation target is `HarnessToolAdapter` and its construction from `OpenAIAgentsRuntime`.

This design applies evidence capture to dynamic harness actions that have a high probability of changing the app-under-test UI:

- `launchApp`
- `killApp`
- `tapOn`
- `performActions`
- `pressKey`
- `inputText`
- `longPressOn`
- `swipe`

## Non-Goals

Do not change strict-core execution. Strict runs already execute through `StepSequenceRunner -> StepRunner` and remain deterministic.

Do not parse dynamic `--case-yaml` input into strict steps. Dynamic raw-case input remains advisory raw text for the LLM.

Do not add a second hand-written evidence protocol inside `HarnessToolAdapter`.

Do not change the dynamic report-layer `evidence-manifest.json` into a full strict-core `EvidenceBundle` in this iteration. Dynamic runs may keep the current report-owned manifest format.

Do not enable generic before/after evidence for read-only or assertion actions in this iteration:

- `assertVisible`
- `assertNotVisible`
- `assert`
- `assertWithAI`
- `uiTree`

`assertWithAI` remains a harness-owned visual assertion that captures its explicit assertion screenshot during invoke. It should not receive this generic side-effect evidence policy.

Do not introduce new public YAML configuration for this iteration.

## Proposed Design

### Approach Selected

Use `StepRunner` inside `HarnessToolAdapter` for dynamic harness actions.

`HarnessToolAdapter` should continue to own SDK function-tool adaptation, JSON argument parsing, schema provenance, tool output formatting, and recorder/report-compatible payload fields. It should stop owning the runner protocol. Once it has built an `ExecutableStep`, it should delegate `prepare -> invoke -> finalize`, `before_action`, `after_action`, failure conversion, and artifact capture to `StepRunner`.

The selected design keeps dynamic execution and strict-core execution aligned at the phase protocol without routing dynamic raw cases through strict YAML parsing.

### Alternatives Considered

#### Approach A: Manual Capture In HarnessToolAdapter

The adapter could manually call `harness.capture_artifact()` before and after direct `harness.invoke_action()`.

Trade-off: This is quick but recreates runner behavior in a second place. It would duplicate phase ordering, failure classification, artifact error handling, and event semantics. It is rejected because it preserves the architectural split that caused the bug.

#### Approach B: HarnessToolAdapter Delegates To StepRunner

The adapter builds the dynamic `ExecutableStep`, applies a dynamic evidence policy for UI-changing actions, then calls `StepRunner.run_step(run_id, step)`.

Trade-off: This reuses the shared runner protocol and keeps strict and dynamic phase behavior coherent. It requires a small output-format bridge because `StepRunner` returns `RunnerStepResult`, while the adapter historically returned JSON derived from `HarnessActionResult`. This is the selected approach.

#### Approach C: New DynamicStepExecutor Abstraction

A new executor could wrap `StepRunner` and own dynamic-only policy such as evidence, retries, timeouts, and recovery.

Trade-off: This may become useful later, but it is heavier than the current need. The first fix should not create a new execution abstraction before dynamic-specific policy has more shape.

## Runtime Flow

The dynamic execution flow should become:

1. `OpenAIAgentsRuntime.run_task()` constructs the platform harness as it does today.
2. `OpenAIAgentsRuntime.run_task()` constructs `HarnessToolAdapter(harness, run_id=run_id, reserved_tool_names=...)`.
3. The adapter discovers harness schemas and builds SDK `FunctionTool` objects as it does today.
4. When the SDK invokes a harness tool, the adapter parses JSON arguments.
5. The adapter maps `HarnessFunctionSchema` into one dynamic `ExecutableStep`.
6. The adapter applies the dynamic side-effect evidence policy when the FSQ action is one of the UI-changing actions listed in this design.
7. The adapter calls `StepRunner(harness).run_step(run_id=run_id, step=step)`.
8. `StepRunner` obtains context, captures before artifacts when enabled, calls `before_action`, invokes the harness action, calls `after_action`, captures after artifacts when enabled, and returns `RunnerStepResult`.
9. The adapter converts `RunnerStepResult` into the existing model-visible harness tool JSON contract plus additional runner evidence fields.
10. OpenAI Agents SDK stream events continue to produce `tool_call_started` and `tool_call_completed` `RunEvent` records.
11. Existing report and strict-recording consumers continue to consume safe event payload fields.

## Dynamic Evidence Policy

`HarnessToolAdapter` should have a narrow internal policy function, for example:

```python
_UI_MUTATING_ANDROID_ACTIONS = {
    "launchApp",
    "killApp",
    "tapOn",
    "performActions",
    "pressKey",
    "inputText",
    "longPressOn",
    "swipe",
}
```

When `action_name` is in this set, the adapter should attach:

```python
EvidencePolicy(
    capture_before=True,
    capture_after=True,
    capture_on_failure=True,
    artifact_kinds=["screenshot", "ui_tree"],
)
```

When `action_name` is not in this set, the adapter should keep the default `EvidencePolicy`.

This allowlist is intentionally explicit. It avoids accidentally adding costly evidence to read-only tools or future platform actions whose semantics are not yet reviewed.

## Tool Output Contract

The adapter must preserve the existing JSON fields because reports and dynamic strict-case recording depend on them:

- `tool_name`
- `tool_origin`
- `platform`
- `driver_method`
- `fsq_action_name`
- `status`
- `failure_category`
- `error_message`
- `duration_ms`
- `result`
- `metadata`

The top-level `status`, `failure_category`, and `error_message` should be derived from the `RunnerStepResult` so artifact capture failures are visible as tool failures.

The `result` field should remain a harness-action-like summary, not be replaced wholesale by `RunnerStepResult`. It should include:

- `status`
- `action_name`
- `output`, when the harness action output is available from the invoke phase metadata,
- `artifact_refs`, flattened from all runner phase reports,
- `error_message`
- `failure_category`
- `metadata`, including schema metadata and harness metadata when available.

The adapter should add these new fields:

- `runner_step_id`
- `runner_result`
- `artifact_refs`

`runner_result` should contain `RunnerStepResult.model_dump(mode="json")`. This gives diagnostics and phase reports without breaking existing consumers.

The top-level `artifact_refs` should duplicate the flattened artifact refs for convenience. The existing report event mapper already knows how to copy `result.artifact_refs` into `RunEvent.payload.artifact_refs`; keeping refs under `result` preserves that compatibility.

## Event And Report Behavior

This iteration does not require dynamic `events.jsonl` to contain raw `RunnerEvent(event_type="artifact_captured")` records as first-class run events. The authoritative new evidence is:

- actual files under the dynamic run directory, especially `artifacts/screenshots` and `artifacts/ui-trees`,
- artifact refs in the harness tool output JSON,
- artifact refs copied into `tool_call_completed` event payloads when the existing event mapper parses the tool output.

The current dynamic report-layer `evidence-manifest.json` may remain minimal. A later design can add a dynamic `EvidenceRecorder` if the project wants strict-core-style evidence bundles for LLM runs.

## Artifact Layout

For a successful dynamic UI-changing action, the expected artifact layout is the existing `ArtifactStore` layout under the dynamic run directory:

```text
<runs_dir>/<run-id>/
  artifacts/
    screenshots/
      <step-id>-prepare-before-action.png
      <step-id>-finalize-after-action.png
    ui-trees/
      <step-id>-prepare-before-action.json
      <step-id>-finalize-after-action.json
```

Exact filenames follow `ArtifactStore` slug normalization, but the refs should distinguish:

- `kind="screenshot"`, `phase="prepare"`, before-action path,
- `kind="ui_tree"`, `phase="prepare"`, before-action path,
- `kind="screenshot"`, `phase="finalize"`, after-action path,
- `kind="ui_tree"`, `phase="finalize"`, after-action path.

For failed UI-changing actions, `StepRunner` may also capture failure artifacts during finalize because `capture_on_failure=True`. That is acceptable and should be visible in `runner_result.phase_reports`.

## Module Ownership

`agent` owns this change because `HarnessToolAdapter` is an agent-runtime adapter between OpenAI Agents SDK tools and the platform harness interface. It already depends on `core` and can reuse `StepRunner` through public core exports.

`core` does not need a new public interface. `StepRunner`, `EvidencePolicy`, `RunnerStepResult`, `StepPhaseReport`, and `ArtifactStore` already model the needed behavior.

`cli` does not need public flag changes. Dynamic `--case-yaml` remains raw text, and `--record` continues to run as a post-run CLI behavior.

`report` does not need to become a strict-core evidence reporter for dynamic runs in this iteration. It may continue to reconstruct tool calls from `events.jsonl`.

`models` should not need new shared models unless implementation finds that output bridging requires a reusable typed model. Prefer private adapter helpers first.

## Error Handling

Expected harness action failures should remain successful SDK tool transport results whose JSON has `status="failed"` and structured failure details. This preserves the existing model feedback loop.

Unexpected adapter failures should still return structured failed tool JSON with:

- `status="failed"`
- `failure_category="harness_error"`
- `error_message`

Artifact capture failures are runner-level failures. If `StepRunner` returns `status="failed"` with `failure_category="artifact_error"`, the adapter should surface that top-level status in the tool JSON. This makes missing `ArtifactStore` or capture backend failures visible instead of silently passing the action.

The dynamic Android harness built by `OpenAIAgentsRuntime` already receives `ArtifactStore(self.settings.output.runs_dir / run_id)`. If an injected test harness lacks artifact capture support, focused tests should use a fake harness that implements `capture_artifact` so the evidence behavior is deterministic.

## Recording Compatibility

Dynamic strict-case recording must continue to work.

The recorder reads `events.jsonl` and reconstructs replayable commands from `tool_call_started` and `tool_call_completed` payloads. It depends on:

- `tool_origin="harness"`
- `fsq_action_name`
- completed tool call status,
- original tool arguments.

This design preserves those fields. Evidence artifact refs should not be written into `recorded.codex.yaml`; they are run evidence, not replay commands.

## Affected Specs Expected To Change

- `fsq_agent/agent/SPEC.md`: update the `_harness_tools.py` responsibility and design decisions so dynamic harness actions execute through `StepRunner` and UI-changing dynamic actions receive before/after screenshot and UI-tree evidence.

No root `SPEC.md`, `core/SPEC.md`, `cli/SPEC.md`, `report/SPEC.md`, or `models/SPEC.md` changes are expected for the first implementation unless spec review finds a public contract mismatch.

## Verification Expectations

Focused tests should cover:

- `HarnessToolAdapter` invokes a dynamic UI-changing action through the runner protocol instead of direct `harness.invoke_action`.
- A dynamic `tapOn` step receives `EvidencePolicy(capture_before=True, capture_after=True, capture_on_failure=True, artifact_kinds=["screenshot", "ui_tree"])`.
- The adapter output preserves existing top-level fields used by reports and recording.
- The adapter output includes flattened artifact refs and a `runner_result`.
- Non-mutating actions such as `assertVisible` or `uiTree` do not receive the generic before/after evidence policy.
- Existing strict runner tests continue to pass.
- Existing dynamic strict recording tests continue to pass.

Real-device acceptance should use the documented dynamic Edge case:

```bash
FSQ_ANDROID_APP_ID=com.microsoft.emmx \
FSQ_ANDROID_SERIAL=<device-serial> \
python3 -m fsq_agent.cli run \
  --config config.example.yaml \
  --case-yaml .fsq-agent-workspace/tmp/dynamic-edge-overflow-tap.codex.yaml \
  --record \
  --record-on-failure \
  --stream-format jsonl \
  --no-tracing
```

Before the fix, the dynamic run should reach a harness `tapOn` tool call but produce no before/after artifacts. After the fix, the same dynamic run should produce screenshot and UI-tree artifacts before and after the Edge `Browser menu` tap.

## Open Questions Resolved

- Approach selected: `HarnessToolAdapter` delegates to `StepRunner`.
- Evidence scope selected: UI-changing dynamic actions, not every harness action.
- Dynamic manifest upgrade: deferred to a later design.
- Configuration: no new user-facing config for this iteration.
- Strict execution: unchanged.

## Handoff

Next step: update `fsq_agent/agent/SPEC.md` to reflect this confirmed design, then write an implementation plan and implement with TDD.
