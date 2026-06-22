# Dynamic Harness Evidence Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify and fix dynamic-mode harness tool execution so a real Edge `tapOn` captures before/after screenshot and UI tree evidence.

**Architecture:** Dynamic CLI runs without `--strict` must keep using `OpenAIAgentsRuntime -> HarnessToolAdapter` for platform actions, but `HarnessToolAdapter` should execute each harness action through the shared runner protocol instead of directly calling `harness.invoke_action()`. The test compares the same real-device dynamic case before and after the adapter change.

**Tech Stack:** Python CLI, OpenAI Agents SDK dynamic runtime, GitHub Copilot provider, Android `uiautomator2` harness, Microsoft Edge Android package `com.microsoft.emmx`, FSQ run artifacts under `.fsq-agent-workspace/output/runs`.

---

## Context

This repository uses Spec-Driven Development. Before coding, read:

- `SPEC.md`
- `fsq_agent/agent/SPEC.md`
- `fsq_agent/core/SPEC.md`
- `fsq_agent/cli/SPEC.md`
- `fsq_agent/observation/SPEC.md`
- `fsq_agent/report/SPEC.md`
- `fsq_agent/models/SPEC.md`

The bug is specifically in the dynamic path. Do not validate this fix with only `--strict`.

The current dynamic path is:

```text
fsq-agent run --case-yaml PATH
  -> cli._run_dynamic()
  -> FsqAgent.from_settings(settings).run(...)
  -> OpenAIAgentsRuntime.run_task(...)
  -> HarnessToolAdapter.build_tools(...)
  -> HarnessToolAdapter._handler_for(...).invoke(...)
  -> harness.get_context()
  -> harness.invoke_action(step, context)
```

The strict path is different:

```text
fsq-agent run --strict --case-yaml PATH
  -> FsqCaseLoader
  -> FsqExecutableStepAdapter
  -> StepSequenceRunner
  -> StepRunner
```

The suspected root cause is that `HarnessToolAdapter` bypasses `StepRunner`, so dynamic mode does not run `prepare` and `finalize` evidence capture around actions.

## Test Principle

Use the same tiny dynamic Edge case before and after modifying `HarnessToolAdapter`.

Before the code change:

- The dynamic run must reach a real harness tool call for `tapOn`.
- The tap should succeed in the real Edge app.
- The run should not contain runner evidence capture for the tap.
- There should be no before/after screenshot and UI tree files associated with the tap step.

After the code change:

- The same dynamic run must still reach a real harness tool call for `tapOn`.
- The tap should still succeed in the real Edge app.
- The run should contain runner evidence capture for the tap.
- The tap step should have four artifacts: before screenshot, before UI tree, after screenshot, and after UI tree.

Final task verification status may be `success` or `failed` depending on the model's final answer and verifier. The acceptance target is the real harness tap call and its evidence capture.

## Files Relevant To The Fix

- Modify: `fsq_agent/agent/_harness_tools.py`
- Likely inspect: `fsq_agent/agent/_openai_runtime.py`
- Likely inspect: `fsq_agent/core/runner/_runner.py`
- Likely inspect: `fsq_agent/core/evidence/_recorder.py`
- Likely inspect: `fsq_agent/core/evidence/_artifact_store.py`
- Likely inspect: `fsq_agent/core/harness/_android.py`
- Test or inspect: `tests/test_openai_runtime.py`
- Test or inspect: `tests/test_step_runner.py`
- Test or inspect: `tests/test_cli.py`
- Test or inspect: `tests/test_strict_case_recording.py`

Do not change strict-mode behavior while fixing dynamic-mode evidence.

## Real Device Preconditions

Use a connected Android device with Edge installed.

Example values from the current workspace:

```bash
export FSQ_ANDROID_APP_ID=com.microsoft.emmx
export FSQ_ANDROID_SERIAL=145e66aa
```

Check device readiness:

```bash
adb devices -l
adb -s "$FSQ_ANDROID_SERIAL" shell pm list packages | rg '^package:com\.microsoft\.emmx$'
adb -s "$FSQ_ANDROID_SERIAL" shell dumpsys window | rg 'mCurrentFocus|mFocusedApp'
```

Expected:

- `adb devices -l` shows one online device.
- Edge package `com.microsoft.emmx` is installed.
- The focused app can be anything before the run.

Provider readiness is required for dynamic mode. The default config uses GitHub Copilot. If the CLI prints a device-code auth prompt, complete the GitHub auth in the browser before continuing. Without provider auth, the run stops before `HarnessToolAdapter` is reached.

## Dynamic Case Fixture

Create a tiny dynamic case input. This file is intentionally used without `--strict`, so the CLI reads it as raw reference text and the LLM chooses harness tools.

Recommended temporary path:

```text
.fsq-agent-workspace/tmp/dynamic-edge-overflow-tap.codex.yaml
```

Content:

```yaml
schemaVersion: fsq.ai-test/v1
name: Dynamic Edge Overflow Tap Evidence Smoke
platform: android
appId: com.microsoft.emmx
---
- launchApp
- tapOn:
    target: Browser menu
    locator:
      resourceId: com.microsoft.emmx:id/overflow_button_bottom
- assertVisible:
    target: Downloads
    locator:
      text: Downloads
- killApp
```

The critical action is the `tapOn` on `com.microsoft.emmx:id/overflow_button_bottom`.

## Baseline Dynamic Run Before Fix

- [ ] **Step 1: Clean up Edge state lightly**

Run:

```bash
adb -s "$FSQ_ANDROID_SERIAL" shell am force-stop "$FSQ_ANDROID_APP_ID"
```

Expected: exit code `0`.

- [ ] **Step 2: Run dynamic mode without `--strict`**

Run:

```bash
FSQ_ANDROID_APP_ID="$FSQ_ANDROID_APP_ID" \
FSQ_ANDROID_SERIAL="$FSQ_ANDROID_SERIAL" \
python3 -m fsq_agent.cli run \
  --config config.example.yaml \
  --case-yaml .fsq-agent-workspace/tmp/dynamic-edge-overflow-tap.codex.yaml \
  --record \
  --record-on-failure \
  --stream-format jsonl \
  --no-tracing
```

Expected:

- The command starts a dynamic run.
- The stream includes `run_started`.
- The stream includes `agent_started`.
- The stream includes dynamic runtime setup events.
- If GitHub Copilot asks for device auth, complete it and allow the command to continue.

Do not add `--strict`.

- [ ] **Step 3: Locate the run directory**

Run:

```bash
RUN_DIR="$(ls -td .fsq-agent-workspace/output/runs/dynamic-edge-overflow-tap-* | head -1)"
printf '%s\n' "$RUN_DIR"
```

Expected: prints the newest dynamic run directory for this fixture.

- [ ] **Step 4: Confirm the run used a real harness tap tool**

Run:

```bash
rg '"type":"tool_call_' "$RUN_DIR/events.jsonl"
rg '"tool_origin":"harness"|"fsq_action_name":"tapOn"|"tool_name":"tap_on"' "$RUN_DIR/events.jsonl"
```

Expected:

- At least one `tool_call_started` and one `tool_call_completed` event.
- At least one harness-origin tool call for the Edge tap action.
- The tap tool output status should be `passed` or should otherwise show that the real harness action was attempted.

If no harness tool call appears, this baseline is invalid because the model did not execute the Edge action. Re-run the same fixture after ensuring provider auth is complete and the device is online.

- [ ] **Step 5: Confirm baseline has no runner evidence capture**

Run:

```bash
find "$RUN_DIR" -path '*/artifacts/*' -type f | sort
rg '"artifact_captured"|before-action|after-action|artifacts/screenshots|artifacts/ui-trees|ui_tree|screenshot' "$RUN_DIR/events.jsonl" "$RUN_DIR/evidence-manifest.json"
```

Expected before the fix:

- `find` prints no screenshot or UI-tree artifact files for the tap.
- `rg` does not show runner `artifact_captured` events.
- If `evidence-manifest.json` exists, it is the dynamic report-layer manifest and should not contain tap before/after screenshot or UI-tree refs.

This is the expected failing behavior.

## Implementation Acceptance Criteria

The implementation should make `HarnessToolAdapter` execute dynamic UI-changing harness actions through the shared runner protocol.

Dynamic UI-changing actions are:

- `launchApp`
- `killApp`
- `tapOn`
- `performActions`
- `pressKey`
- `inputText`
- `longPressOn`
- `swipe`

Read-only/assertion actions should not receive generic before/after capture in this iteration:

- `assertVisible`
- `assertNotVisible`
- `assert`
- `assertWithAI`
- `uiTree`

The adapter must preserve the existing dynamic tool output contract used by reports and strict recording:

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

The adapter must also expose enough runner evidence in dynamic outputs or run files for post-run inspection.

For a successful dynamic `tapOn`, acceptance requires these artifacts under the dynamic run directory:

```text
artifacts/screenshots/<tap-step-id>-prepare-before-action.png
artifacts/ui-trees/<tap-step-id>-prepare-before-action.json
artifacts/screenshots/<tap-step-id>-finalize-after-action.png
artifacts/ui-trees/<tap-step-id>-finalize-after-action.json
```

Exact filenames may vary according to `ArtifactStore` normalization, but the artifact refs must identify:

- `kind="screenshot"`, `phase="prepare"`, `reason="before-action"`
- `kind="ui_tree"`, `phase="prepare"`, `reason="before-action"`
- `kind="screenshot"`, `phase="finalize"`, `reason="after-action"`
- `kind="ui_tree"`, `phase="finalize"`, `reason="after-action"`

Use the shared `EvidencePolicy` on dynamic tool-created `ExecutableStep` values for UI-changing actions:

```python
EvidencePolicy(
    capture_before=True,
    capture_after=True,
    capture_on_failure=True,
    artifact_kinds=["screenshot", "ui_tree"],
)
```

Do not apply this policy to assertion or observation actions unless a later confirmed design expands the scope.

## Dynamic Run After Fix

- [ ] **Step 1: Clean up Edge state lightly**

Run:

```bash
adb -s "$FSQ_ANDROID_SERIAL" shell am force-stop "$FSQ_ANDROID_APP_ID"
```

Expected: exit code `0`.

- [ ] **Step 2: Run the exact same dynamic command**

Run:

```bash
FSQ_ANDROID_APP_ID="$FSQ_ANDROID_APP_ID" \
FSQ_ANDROID_SERIAL="$FSQ_ANDROID_SERIAL" \
python3 -m fsq_agent.cli run \
  --config config.example.yaml \
  --case-yaml .fsq-agent-workspace/tmp/dynamic-edge-overflow-tap.codex.yaml \
  --record \
  --record-on-failure \
  --stream-format jsonl \
  --no-tracing
```

Expected:

- The command starts a dynamic run.
- The model reaches the same real Edge `tapOn` harness tool call.
- The tool output contract remains JSON parseable.

- [ ] **Step 3: Locate the new run directory**

Run:

```bash
RUN_DIR="$(ls -td .fsq-agent-workspace/output/runs/dynamic-edge-overflow-tap-* | head -1)"
printf '%s\n' "$RUN_DIR"
```

Expected: prints the newest run directory, different from the baseline run directory.

- [ ] **Step 4: Confirm the harness tap still happened**

Run:

```bash
rg '"type":"tool_call_' "$RUN_DIR/events.jsonl"
rg '"tool_origin":"harness"|"fsq_action_name":"tapOn"|"tool_name":"tap_on"' "$RUN_DIR/events.jsonl"
```

Expected:

- At least one harness `tapOn`/`tap_on` tool call.
- Tool output status for the tap is `passed`.

- [ ] **Step 5: Confirm evidence capture exists**

Run:

```bash
find "$RUN_DIR/artifacts" -type f | sort
rg '"artifact_captured"|before-action|after-action|artifacts/screenshots|artifacts/ui-trees|ui_tree|screenshot' "$RUN_DIR" -g '*.json' -g '*.jsonl' -g '*.md'
```

Expected after the fix:

- At least two screenshot files exist under `artifacts/screenshots`.
- At least two UI-tree JSON files exist under `artifacts/ui-trees`.
- The evidence metadata associates these artifacts with the dynamic tap step.
- The metadata distinguishes prepare/before-action from finalize/after-action.

- [ ] **Step 6: Confirm recording still works**

Run:

```bash
find "$RUN_DIR" -maxdepth 2 -type f \( -name 'recorded.codex.yaml' -o -name 'recording.json' \) -print | sort
```

Expected:

- `recording.json` exists when `--record` was provided.
- If the run was replayable, `recorded.codex.yaml` exists.
- The recorded YAML must not embed screenshot or UI-tree contents.
- Dynamic evidence artifacts must not break strict case recording.

## Automated Regression Tests To Add Or Update

Real-device dynamic runs are the acceptance test, but coding should still add fast regression coverage.

- [ ] **Step 1: Add or update a focused adapter test**

Target file:

```text
tests/test_openai_runtime.py
```

or a new focused file:

```text
tests/test_harness_tool_adapter.py
```

Test intent:

- Build a harness adapter for a harness exposing `tap_on`.
- Invoke the generated tool handler directly.
- Assert the adapter returns a JSON payload preserving existing harness tool fields.
- Assert the handler calls the runner path, including before/after artifact capture for a tap step.

- [ ] **Step 2: Verify the test fails before implementation**

Run:

```bash
pytest tests/test_harness_tool_adapter.py -q
```

or:

```bash
pytest tests/test_openai_runtime.py -q
```

Expected before implementation: failure showing missing before/after evidence capture.

- [ ] **Step 3: Implement the adapter change**

Modify:

```text
fsq_agent/agent/_harness_tools.py
```

The implementation should avoid duplicating runner phase logic. Prefer calling `StepRunner.run_step()` and converting `RunnerStepResult` plus flattened artifact refs into the existing harness tool JSON output.

- [ ] **Step 4: Verify focused tests pass**

Run:

```bash
pytest tests/test_harness_tool_adapter.py tests/test_openai_runtime.py -q
```

Expected: pass.

- [ ] **Step 5: Verify strict behavior did not regress**

Run:

```bash
pytest tests/test_step_runner.py tests/test_step_sequence_runner.py tests/test_cli_core_execution.py tests/test_strict_case_recording.py -q
```

Expected: pass.

## Common Failure Modes

- If the dynamic run never emits a harness `tool_call_completed`, the model did not execute the Edge action. This is not valid evidence for or against the adapter fix.
- If the CLI stops at GitHub Copilot device auth, complete auth first. Otherwise the run has not reached dynamic runtime execution.
- If `config.local.yaml` is missing, use `config.example.yaml` for this verification unless the local machine has a proper private config.
- If `.vscode/launch.json` points to `.venv/Scripts/python.exe` on macOS, run the equivalent terminal command with `python3 -m fsq_agent.cli`.
- If strict mode passes but dynamic mode has no artifacts, that still confirms the bug is in the dynamic harness adapter path.
- If dynamic artifacts exist but strict recording fails, fix the recording compatibility before closing the task.

## Done Criteria

The task is done only when all are true:

- The pre-fix dynamic baseline was observed or the failing adapter test proves the current behavior.
- `HarnessToolAdapter` no longer bypasses the runner protocol for the target dynamic harness action.
- The same real-device dynamic Edge tap run produces before/after screenshot and UI-tree artifacts.
- Existing tool output fields used by reports and dynamic strict recording remain present.
- Focused adapter tests pass.
- Relevant strict-core and recording tests pass.
- Relevant `SPEC.md` files are updated and confirmed if the implementation changes public behavior or module contracts.
- A diff-based SPEC implementation audit has been performed before claiming completion.
