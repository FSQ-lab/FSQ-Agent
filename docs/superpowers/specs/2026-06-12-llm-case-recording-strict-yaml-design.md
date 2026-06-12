# LLM Case Recording To Strict YAML Design

Date: 2026-06-12

## Goal

Allow a dynamic LLM run to emit a replayable FSQ `.codex.yaml` artifact that can later be executed with strict deterministic execution:

```bash
fsq-agent run --strict --case-yaml <recorded-case>
```

The recorded artifact must be based on what actually happened during the dynamic run, including replayable CommonTool dependencies such as runtime secrets and pure waits, while keeping secret values out of YAML, logs, reports, and manifests.

## Scope

This feature applies to dynamic LLM runs only:

- `fsq-agent run --goal ... --record`
- `fsq-agent run --case-yaml ... --record`
- `fsq-agent run --case-dir ... --record`

The CLI adds two run flags:

- `--record`: record a strict-case artifact after an eligible dynamic run.
- `--record-on-failure`: allow draft recording for `failed` or `inconclusive` dynamic runs. This flag is valid only with `--record`.

Default recording eligibility:

- `success` plus `--record`: write a validated recorded case.
- `failed` or `inconclusive` plus `--record --record-on-failure`: write a draft-marked recorded case when enough replayable evidence exists.
- Any other status or flag combination: do not write a recorded case.

Recorded files are written under each dynamic run directory, never under the read-only `cases.dir` and never by mutating the source case file.

## Non-Goals

- Do not update root or module `SPEC.md` files in this phase.
- Do not implement the feature in this phase.
- Do not let the LLM agent write the strict case file during the run.
- Do not mutate source `.codex.yaml` files.
- Do not enable strict-mode recording. `run --strict` continues to consume authored deterministic YAML exactly as provided.
- Do not synthesize setup, teardown, locator fallback, testcase repair, or assertions that did not happen during the dynamic run.
- Do not record arbitrary CommonTool calls. Version 1 records only `get_runtime_secret` and `wait_ms` as replayable CommonTool dependencies.

## Proposed Design

### CLI Interface

`cli` owns the public flags, validation, orchestration, and user-facing path output.

Validation rules:

- `--record` is accepted only for dynamic runs.
- `--record-on-failure` requires `--record`.
- `--strict --record` is invalid.
- `--strict --record-on-failure` is invalid.
- Recording failures should not change the dynamic run result status, but they should be printed clearly and included in directory-run summaries.

Output layout for a single dynamic run:

```text
<runs_dir>/<run-id>/
  events.jsonl
  report.md
  report.json
  recorded.codex.yaml
  recording.json
```

For dynamic `--case-dir`, each individual dynamic case run writes its own `recorded.codex.yaml` and `recording.json` when eligible. The directory summary includes each recording status, recorded path, warnings, and errors.

### Module Ownership

- `cli`: public flags, eligibility checks, output messages, directory-run summary updates, and the strict-recording helper entry point.
- `cli._strict_case_recording` or similarly named internal helper: converts one run directory plus task/run metadata into `recorded.codex.yaml` and `recording.json`.
- `agent`: unchanged responsibility. It continues to execute dynamic runs and persist run events. It does not write case files or own recording policy.
- `tools`: continues to own CommonTool safety policy. It may need richer safe event metadata for replayable CommonTool calls.
- `fsq`: validates the generated case and converts it into strict-core executable steps.
- `models`: owns any new shared replay-reference models required by FSQ parsing and strict replay.
- `core`: remains the deterministic execution boundary. It should receive already-resolved in-memory parameters for strict replay.
- `report`: optional integration only. The minimum design writes `recording.json` and prints CLI paths; a later SPEC update may also include recorded-case paths in reports.

### Recording Source

The recorder is a post-run event-log recorder. It reads persisted dynamic run evidence, primarily `events.jsonl`, after the LLM run completes.

The recorder reconstructs logical tool calls from `tool_call_started`, `tool_call_completed`, and `tool_call_failed` events. It preserves event sequence order and deduplicates duplicate CommonTool events if both SDK stream events and CommonTool adapter events describe the same logical call.

The recorder ignores reasoning summaries, model messages, verifier events, runtime progress, report generation, artifact reads used only for diagnosis, and failed tool calls except when a failed dynamic run is explicitly recorded as a draft and the failed calls are needed for warnings.

### Harness Action Recording

Harness-origin calls become FSQ command entries when all of these are true:

- The call has `tool_origin == "harness"`.
- The call has an `fsq_action_name` payload value.
- The action exists in `ANDROID_ACTION_DEFINITIONS_BY_NAME`.
- The call completed successfully at the tool transport level.
- The harness output status, when structured status metadata is available, indicates a passed or successful action.
- The arguments validate against the strict replay parameter contract for that action.

The generated FSQ action name comes from `fsq_action_name`, not from the snake-case SDK tool name. The generated payload comes from the recorded tool arguments after replay references are applied.

Unsupported harness calls are skipped and recorded as warnings. If no valid commands remain, the recorder writes no `.codex.yaml` and records a failed recording result.

### Replayable CommonTool Support

Version 1 supports replay for exactly two CommonTools:

- `get_runtime_secret`
- `wait_ms`

Other CommonTools remain diagnostic context and are not replayed:

- `read_file`
- `write_file`
- `search_artifact`
- `read_artifact_slice`

Skipped CommonTools are listed in `recording.json` with tool name and sequence context.

#### Runtime Secret Replay

The generated YAML must never contain secret values. It may contain only the environment variable names that strict replay should resolve at execution time.

Design syntax for a secret-backed parameter field:

```yaml
- inputText:
    text:
      runtimeSecret: TEST_ACCOUNT_PASSWORD
    target: Password field
    locator:
      resourceId: com.example:id/password
```

Binding rules:

- A successful `get_runtime_secret` call records the requested environment variable name as an active replay dependency.
- When a subsequent harness action contains a redacted argument value such as `***`, the recorder may replace that field with `{runtimeSecret: <name>}` only when exactly one active secret dependency can explain the redacted value.
- If multiple secrets are active and the redacted harness field cannot be mapped unambiguously, recording fails for that run.
- If a redacted harness argument appears with no matching runtime secret dependency, recording fails for that run.
- The recorder writes required runtime secret names to case metadata and to `recording.json`.

Strict replay rules:

- The strict entry layer validates every referenced secret name against `runtime_secrets.allowed_env_names` before UI actions begin.
- The strict entry layer validates that each referenced environment variable is present before UI actions begin.
- The strict entry layer resolves `{runtimeSecret: NAME}` to the secret value only in memory before invoking the harness.
- Resolved secret values must not be written to generated YAML, event previews, evidence manifests, reports, or recording manifests.
- If strict evidence or harness metadata could include resolved parameters, that metadata must be redacted before persistence.

#### Wait Replay

Design syntax for replaying a pure wait:

```yaml
- waitMs:
    duration_ms: 1000
    reason: post-submit settle
```

Rules:

- A successful `wait_ms` call is recorded as `waitMs` in the same relative order as harness actions.
- `waitMs` is a strict replay command that performs a pure elapsed-time wait without touching platform state.
- The command is replayable in strict mode and should not be routed through Android driver gesture APIs.
- `duration_ms` remains bounded by the CommonTool wait constraints.

### Generated YAML Shape

Example recorded case:

```yaml
schemaVersion: fsq.ai-test/v1
name: Sign in smoke test
description: Recorded from dynamic LLM run sign-in-smoke-2026-06-12_10-30-00.
platform: android
appId: com.microsoft.emmx
tags:
  - recorded
  - llm-run
  - strict-candidate
properties:
  recording:
    sourceRunId: sign-in-smoke-2026-06-12_10-30-00
    sourceTaskId: sign-in-smoke
    sourceStatus: success
    draft: false
    requiredRuntimeSecrets:
      - TEST_ACCOUNT_PASSWORD
    warnings: []
---
- launchApp: {}
- inputText:
    text:
      runtimeSecret: TEST_ACCOUNT_PASSWORD
    target: Password field
    locator:
      resourceId: com.example:id/password
- waitMs:
    duration_ms: 1000
    reason: post-submit settle
- assertVisible:
    target: Signed in account menu
- killApp: {}
```

For draft recordings from `--record-on-failure`, metadata uses:

```yaml
tags:
  - recorded
  - llm-run
  - strict-candidate
  - draft-recording
properties:
  recording:
    draft: true
```

### Recording Manifest

`recording.json` is written next to `recorded.codex.yaml` whenever recording is attempted. It contains no secret values.

Minimum shape:

```json
{
  "run_id": "sign-in-smoke-2026-06-12_10-30-00",
  "task_id": "sign-in-smoke",
  "source_status": "success",
  "recording_status": "success",
  "recorded_case_path": "recorded.codex.yaml",
  "draft": false,
  "command_count": 5,
  "required_runtime_secrets": ["TEST_ACCOUNT_PASSWORD"],
  "warnings": [],
  "skipped_tool_calls": [],
  "validation": {
    "fsq_loader": "passed",
    "fsq_step_adapter": "passed"
  }
}
```

When recording fails, `recording_status` is `failed`, `recorded_case_path` is `null`, and `errors` explains the cause.

### Validation Pipeline

After writing `recorded.codex.yaml`, the recorder must validate it before printing it as a usable strict candidate:

1. Load with `FsqCaseLoader`.
2. Convert with `FsqExecutableStepAdapter`.
3. Validate replay references, including `runtimeSecret` references and `waitMs` commands.
4. Confirm strict replay can resolve required runtime secret names from configuration and environment when validation runs in an execution context.

The recorder may write a structurally valid draft for failed or inconclusive runs, but CLI output must distinguish draft artifacts from successful recorded strict candidates.

## Data And Control Flow

```text
dynamic run
  -> agent persists events.jsonl
  -> verifier computes TaskResult.status
  -> report generation writes report.md/json
  -> cli checks --record eligibility
  -> recorder reads events.jsonl
  -> recorder builds replay trace
       -> get_runtime_secret dependencies
       -> waitMs commands
       -> harness FSQ commands
  -> recorder writes recorded.codex.yaml
  -> recorder writes recording.json
  -> recorder validates generated YAML through fsq strict parser/adapter
  -> cli prints recording path or warning
```

Strict replay control flow for secret refs:

```text
strict CLI loads recorded.codex.yaml
  -> fsq parser preserves runtimeSecret refs
  -> strict entry validates allowed env names and presence
  -> strict entry resolves refs in memory
  -> strict entry passes resolved ExecutableStep params to StepSequenceRunner
  -> evidence/report persistence redacts resolved secret values
```

## Error Handling And Edge Cases

- Missing or conflicting run inputs keep existing behavior.
- `--record-on-failure` without `--record` fails before execution.
- Record flags with `--strict` fail before execution.
- Recording failure after a dynamic run does not alter the dynamic run's status.
- A run with no valid replayable commands writes no `.codex.yaml`.
- A run with no assertion commands writes YAML with a warning instead of inventing an assertion.
- A run with no setup or teardown commands writes YAML with a warning instead of inventing lifecycle commands.
- Unsupported harness calls are skipped and warned.
- Unsupported CommonTool calls are skipped as diagnostics and warned only when they appear likely to affect replay.
- Ambiguous secret binding fails recording for that run.
- Missing strict replay secret configuration fails before UI actions begin.
- Existing `recorded.codex.yaml` in the run directory causes recording to fail for that run rather than silently overwriting.
- Directory runs continue after per-case recording failures and report each recording outcome.

## Affected Specs Expected To Change

Root `SPEC.md`:

- Mention dynamic-run strict case recording as an SDD-covered public behavior.
- Add or update module responsibilities for CLI-owned recording and strict replay refs.

`fsq_agent/cli/SPEC.md`:

- Add `--record` and `--record-on-failure` to dynamic run public interface.
- Define validation rules and output paths.
- Define internal recording helper responsibilities.
- Define strict replay reference resolution at the entry boundary.

`fsq_agent/fsq/SPEC.md`:

- Accept generated replay syntax for `runtimeSecret` parameter refs.
- Accept `waitMs` as a replayable strict command.
- Preserve or normalize replay refs without resolving secret values.
- Continue to reject malformed commands before execution.

`fsq_agent/models/SPEC.md`:

- Add shared replay-reference models if needed, such as a runtime secret reference model.
- Update Android action parameter contracts or adapter contracts so secret refs can validate before strict entry resolution.
- Add a `waitMs` command model or shared executable-step representation for pure waits.

`fsq_agent/tools/SPEC.md`:

- Mark `get_runtime_secret` and `wait_ms` as recordable replay dependencies.
- Define safe event metadata needed by the recorder without exposing secret values.
- Confirm other CommonTools are diagnostic-only for recording v1.

`fsq_agent/core/SPEC.md`:

- Define how strict pure waits execute without platform side effects.
- Define evidence redaction expectations when strict entry resolves secret-backed params in memory.

`fsq_agent/agent/SPEC.md`:

- Clarify that agent runtime persists enough event metadata for recording, but does not write recorded case files.
- Clarify harness/CommonTool event metadata used by CLI recording.

`fsq_agent/report/SPEC.md`:

- Optional: include recorded case path and recording status in LLM reports. This is not required for the first implementation if CLI output and `recording.json` are sufficient.

`fsq_agent/config/SPEC.md`:

- Clarify that strict replay validates `runtimeSecret` refs against `runtime_secrets.allowed_env_names` and environment presence before UI actions.

## Open Questions Resolved During Discussion

- CLI flag names are `--record` and `--record-on-failure`.
- `--record` is a boolean flag that auto-writes into the run directory.
- By default, recording writes only for successful dynamic runs.
- Failed and inconclusive runs require `--record-on-failure` and are marked as draft.
- Recorded commands represent the actual successful execution path, not an abstracted original intent path.
- No assertions are invented. Missing assertions produce warnings.
- Version 1 CommonTool replay supports only `get_runtime_secret` and `wait_ms`.
- Runtime secret values are never written to generated YAML. YAML stores env var names through `runtimeSecret` refs.

No independent subsystem split is needed for this design because the changes support one end-to-end feature: recording a dynamic LLM execution into a strict-runnable replay artifact.

## Verification Expectations

Unit tests:

- CLI rejects `--record-on-failure` without `--record`.
- CLI rejects `--record` and `--record-on-failure` with `--strict`.
- CLI writes `recorded.codex.yaml` for successful dynamic runs with `--record`.
- CLI does not write `recorded.codex.yaml` for failed dynamic runs unless `--record-on-failure` is present.
- Directory runs continue when one recording attempt fails.
- Recorder preserves harness action order and maps snake-case tool names to FSQ action names through `fsq_action_name`.
- Recorder filters CommonTools that are not replayable in v1.
- Recorder records `wait_ms` as `waitMs`.
- Recorder binds `get_runtime_secret` to redacted harness args as `{runtimeSecret: NAME}`.
- Recorder fails on ambiguous secret binding.
- Recorder fails on redacted harness args with no matching runtime secret.
- Recorder warns, but still writes, when no assertion action is recorded.

Strict replay tests:

- Strict replay resolves `{runtimeSecret: NAME}` in memory.
- Strict replay rejects unallowlisted secret names before UI actions begin.
- Strict replay rejects missing env values before UI actions begin.
- Strict replay does not leak secret values into YAML, run events, evidence manifests, core reports, LLM reports, or `recording.json`.
- Strict replay executes `waitMs` as a pure wait without platform driver calls.

Integration-style tests with fakes:

- A fake dynamic run emits `get_runtime_secret`, `input_text` with a redacted text arg, `wait_ms`, `assert_visible`, and completion. `--record` writes a generated case that reloads through `FsqCaseLoader` and converts through `FsqExecutableStepAdapter`.
- A fake strict run loads the recorded case, resolves the secret ref from env, and passes only in-memory resolved params to the fake harness.

Audit expectations:

- Before completion, run the independent diff-based SPEC implementation audit required by the repository SDD rules.
- The audit must confirm that implementation follows updated `SPEC.md` files, not this design document directly.
- The audit must confirm no source case mutation, no agent-authored case-file writing, and no persisted secret values.