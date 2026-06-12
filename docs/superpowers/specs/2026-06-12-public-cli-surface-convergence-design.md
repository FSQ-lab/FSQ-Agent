# Public CLI Surface Convergence Design

Date: 2026-06-12

## Goal

Converge fsq-agent's externally supported behavior around three CLI commands and remove code that no longer serves those paths.

The public product surface should become:

- `fsq-agent init`: initialize the workspace and run configuration/readiness checks.
- `fsq-agent run`: execute either the default LLM-driven goal workflow or, with `--strict`, the deterministic strict-core workflow.
- `fsq-agent report`: print a previously generated run report, regardless of whether the run came from the LLM path or strict-core path.

The two externally supported execution modes are:

1. Dynamic LLM execution through CLI. The user provides a goal source. The source can be a one-sentence goal, one YAML case file read as complete raw text, or all case files under a directory read one file at a time as complete raw text. The LLM agent dynamically plans and executes from that goal/reference content.
2. Strict-core execution through CLI. The user provides one YAML case file or a directory of YAML case files. The case is parsed as FSQ YAML and executed through the existing deterministic core path without LLM involvement.

## Scope

In scope:

- Replace the many public CLI execution and diagnostic commands with `init`, `run`, and `report`.
- Make `run` the single public execution entry point.
- Make normal `run` always mean dynamic LLM goal execution.
- Make `run --strict` mean deterministic strict-core execution with no LLM, no AI assertion evaluator, no locator fallback, no action repair, and no testcase mutation.
- Read dynamic `--case-yaml` file input as raw text only. Do not parse, normalize, extract key actions, validate FSQ schema, or derive final verification criteria from YAML in the LLM path.
- Support dynamic directory execution by reading each `*.codex.yaml` file under `--case-dir` as raw text and running one LLM task per file serially.
- Support strict directory execution by parsing each `*.codex.yaml` file under `--case-dir` and running one strict-core case per file serially.
- Move Android device/app selection for strict mode entirely into config.
- Extend `report` so it can find either LLM reports or strict-core reports by run id.
- Delete public commands and internal code that no longer serve `init`, `run`, `report`, or the runtimes behind them.

## Non-Goals

- Do not implement code during this design step.
- Do not update root or module `SPEC.md` files during this design step.
- Do not keep old command names as compatibility aliases.
- Do not keep standalone `pre-plan`, `capabilities`, `validate-config`, `run-goal`, `run-batch`, `run-strict-core`, or `run-strict-core-batch` as public commands.
- Do not support inline YAML content as a command-line argument or stdin input in this design.
- Do not expose a public mode switch for the LLM path; normal `run` is the only LLM path.
- Do not add recovery/self-healing to strict-core execution.
- Do not unify the internal report data models. LLM and strict-core reports may remain different internally as long as `report` provides one public lookup command.

## Approaches Considered

### Approach 1: Keep Existing Commands And Document The Preferred Ones

This keeps all current commands and tells users to prefer `run`, `run-goal`, and `run-strict-core` selectively.

Trade-off: lowest implementation risk, but it does not actually converge the product. It leaves duplicate workflows and public concepts in place.

### Approach 2: Add New Command Names Such As `run-agent` And `run-core`

This creates clearer names for the two execution engines.

Trade-off: the behavior is explicit, but the CLI still exposes multiple execution commands. It also adds another naming migration instead of simplifying around the existing `run` verb.

### Approach 3: Single `run` Command With `--strict` For Deterministic Execution

This makes `run` the only public execution entry. Normal `run` is LLM-driven goal execution. `run --strict` is deterministic strict-core execution.

Trade-off: the command has one important flag, but the public model is simple: all execution starts from `run`, and strictness controls whether the LLM participates.

Chosen approach: Approach 3.

## Proposed Design

### Public Command Surface

The CLI command group should expose only:

```text
fsq-agent init
fsq-agent run
fsq-agent report
```

The following commands should be removed from the public click command group:

```text
validate-config
capabilities
pre-plan
run-goal
run-batch
run-strict-core
run-strict-core-batch
```

No compatibility aliases should be kept. Documentation, examples, tests, and help output should point to the three-command surface only.

### `init`

`init` replaces the previous separate initialize and validate-config behaviors.

Expected behavior:

- Load and normalize settings from `--config` and `--workspace`.
- Create or verify the managed workspace and output directories according to existing workspace settings.
- Validate static configuration schema.
- Run readiness checks for the LLM path, including OpenAI Agents SDK provider settings and credentials when available.
- Run readiness checks for strict-core Android config, including platform/backend/app id settings and any configured device serial.
- Print concise status for LLM readiness and strict-core readiness.
- Exit nonzero when config cannot be loaded, workspace initialization fails, or static configuration is invalid.
- Let `run` perform selected-mode hard failures when a mode-specific dependency is missing. For example, a user with valid strict-core config but no OpenAI credentials should still be able to initialize and later run `run --strict`.

This keeps `init` useful for both execution modes without requiring strict-only users to configure an LLM provider.

### `run` Input Contract

Exactly one input source is required:

```text
--goal TEXT
--case-yaml PATH
--case-dir PATH
```

Input rules:

- `--goal` is valid only for the default LLM path.
- `--case-yaml` is valid for both default LLM and strict modes.
- `--case-dir` is valid for both default LLM and strict modes.
- `--goal`, `--case-yaml`, and `--case-dir` are mutually exclusive.
- `--strict --goal` is invalid because strict-core needs authored YAML steps.
- Relative `--case-yaml` and `--case-dir` values should resolve against configured `cases.dir` first, then the current working directory, preserving the existing case-path convenience.
- Directory runs should discover `*.codex.yaml` files recursively, sort them for deterministic order, and execute serially because UI automation shares external device/app state.

Normal `run` remains stream-capable for LLM progress events. Strict mode may print concise per-case progress and generated paths, but it should not expose LLM streaming options because no LLM participates.

### Default LLM Run Mode

Normal `fsq-agent run` is goal execution. There is no separate run mode for parsed FSQ agent tasks.

Input conversion:

- `--goal TEXT` creates one dynamic goal task from the normalized text.
- `--case-yaml PATH` reads the entire file as UTF-8 text and creates one dynamic goal task whose description includes the source path and raw file content.
- `--case-dir PATH` reads each discovered case file as UTF-8 text and creates one dynamic goal task per file.

Important constraint: the LLM path must not parse YAML into `FsqCase`, must not use `FsqTaskAdapter`, must not extract ordered key actions, and must not locally classify YAML commands as final verification criteria. The YAML file content is reference material for the LLM, not a structured local contract in this mode.

Task shape:

- The task id should be a stable slug derived from the goal text or case file path, plus a timestamp or run-level suffix when needed to avoid output collisions.
- The task name should be the goal text for `--goal` and the case file stem or metadata-free source label for `--case-yaml`.
- The task description should clearly state that raw case content is execution reference material and that the agent should dynamically plan and execute toward the intended scenario.
- Dynamic inputs should receive goal-level blocking verification only. For `--goal`, the goal text is the verification target. For `--case-yaml` and `--case-dir`, the intended scenario represented by the raw file content and source path is the verification target. The CLI layer must not invent local operation or assertion criteria by parsing YAML.

Internal model planning may remain part of `FsqAgent.run` if it is needed for dynamic execution. Standalone pre-planning should not remain a public CLI command or public module export. Any retained pre-planning implementation must be reachable from the normal LLM run path; otherwise it should be deleted.

### Strict-Core Run Mode

`fsq-agent run --strict` executes authored YAML through the deterministic core path.

Input conversion:

- `--case-yaml PATH` loads and validates one FSQ `.codex.yaml` case with `FsqCaseLoader`.
- `--case-dir PATH` loads and validates discovered FSQ `.codex.yaml` cases serially.
- Each case is converted to `ExecutableStep` records through `FsqExecutableStepAdapter`.
- Steps execute through `StepSequenceRunner` with `AndroidHarness`, `ArtifactStore`, and the configured Android driver.
- A core evidence manifest and core report are generated per case.

Strict mode config:

- Strict mode reads Android platform, backend, app id, and serial configuration from config only.
- CLI options such as `--android-serial`, `--app-id`, `--run-id`, `--run-prefix`, and `--enable-ai-assertions` should not be public options.
- If app id is absent from config, strict mode may still use `appId` from case metadata. If neither exists, strict mode fails before execution with a clear configuration error.
- If a device serial is absent, behavior follows the configured Android backend's supported default-device behavior. If the backend cannot select a device, strict mode fails with a clear configuration error.

No LLM rule:

- `run --strict` must not validate OpenAI provider credentials, construct `OpenAIAssertionEvaluator`, call any LLM runtime, or use AI-assisted assertion evaluation.
- Authored `assertWithAI` cannot be satisfied through an LLM in strict mode. The implementation should fail such cases clearly before or at the authored step rather than silently enabling AI.

### Directory Execution

Directory execution is serial in both modes.

LLM directory execution:

- Each case file becomes an independent dynamic goal task.
- Each task creates its own run id, event log, report, and artifact directory.
- Execution continues after failed cases and prints a final summary.
- The summary is operational only; individual reports remain authoritative.

Strict directory execution:

- Each case file becomes an independent strict-core run.
- Each run writes its own `evidence-manifest.json`, `core-report.md`, and `core-report.json`.
- Execution continues after failed cases and writes a directory-run summary under a batch run directory or equivalent summary location.
- A strict directory run exits nonzero if any case fails.

### `report`

`report` remains a read-only command that prints an existing report by run id.

Expected behavior:

- `fsq-agent report --run-id ID --format markdown|json` looks under the configured runs directory.
- For Markdown, it finds `report.md` for LLM runs or `core-report.md` for strict-core runs.
- For JSON, it finds `report.json` for LLM runs or `core-report.json` for strict-core runs.
- If exactly one matching report exists, print it.
- If no matching report exists, fail with a concise not-found error that lists the checked paths.
- If both LLM and strict-core reports exist under the same run id, fail with an ambiguity error. This should be rare because unified run id generation should avoid collisions.

The internal LLM and strict-core report generators can remain separate because their evidence sources and report content are different.

## Module Ownership

### `cli`

Own the public command group and input conversion at the entry boundary.

Expected changes:

- Update `SPEC.md` to list only `init`, `run`, and `report` as public commands.
- Replace multiple command handlers with one execution handler that dispatches on `--strict`.
- Add raw goal-source loading for `--goal`, `--case-yaml`, and `--case-dir` in normal LLM mode.
- Keep strict-core composition helpers only if they are used by `run --strict`.
- Remove standalone command formatting/helpers that are only used by deleted commands.

### `agent`

Own dynamic LLM execution only.

Expected changes:

- Treat normal CLI execution as goal/reference-driven dynamic execution.
- Stop exposing standalone pre-plan as a public CLI/API surface; keep only implementation code that is directly invoked by normal LLM `FsqAgent.run`.
- Keep internal model planning only if it is part of `FsqAgent.run`.
- Do not accept parsed FSQ command-derived key actions from the CLI path for dynamic YAML-file execution.

### `fsq`

Own strict FSQ YAML loading and executable-step conversion.

Expected changes:

- Keep `FsqCaseLoader` and `FsqExecutableStepAdapter` for strict-core execution.
- Remove `FsqTaskAdapter` from the public interface and delete it if no internal caller remains.
- Clarify that raw YAML-as-reference for LLM execution is owned by `cli`, not `fsq`, because it deliberately avoids parsing.

### `core`

Continue to own deterministic strict-core execution contracts.

Expected changes:

- Preserve strict execution through `StepRunner`, `StepSequenceRunner`, `AndroidHarness`, configured drivers, `EvidenceRecorder`, and `ArtifactStore`.
- Clarify that `run --strict` does not enable AI assertion evaluation.
- Preserve failure behavior for unsupported authored steps such as `assertWithAI` when no evaluator is configured.

### `config`

Own mode-specific readiness data.

Expected changes:

- Ensure config contains enough Android harness settings for strict-core execution without CLI device/app overrides.
- Keep OpenAI provider settings for default LLM run mode.
- Allow `init` to report readiness for both modes without forcing strict-only users to configure LLM credentials.

### `report`

Own the two existing report generation paths and the unified lookup behavior used by CLI.

Expected changes:

- Keep `ReportGenerator` for LLM task reports.
- Keep `CoreEvidenceReportGenerator` for strict-core evidence reports.
- Add or expose a lookup helper that resolves a run id to either report family.

### `models`

Own shared task, result, settings, FSQ, core, and report models that remain reachable.

Expected changes:

- Keep `Task` and verification models needed by dynamic LLM execution.
- Keep FSQ and core models needed by strict-core execution.
- Remove public exports for models that become unreachable after command/API removal, only after usage analysis confirms they are not needed by retained internals.

## Deletion Plan

Implementation should delete code in dependency order after SPEC updates are confirmed:

1. Remove public click commands for deleted features.
2. Delete command-only helpers such as standalone pre-plan formatting and capability table formatting if no retained command uses them.
3. Remove `FsqTaskAdapter` and associated tests when dynamic YAML execution no longer parses FSQ into `Task` objects.
4. Remove standalone pre-plan public exports/tests; keep only implementation tests for pre-planning code that remains directly invoked by normal LLM execution.
5. Remove strict-core AI assertion CLI wiring, including `--enable-ai-assertions`, from the strict execution entry.
6. Remove README examples and tests for deleted commands.
7. Run import/reference searches to delete only code that is no longer reachable from `init`, `run`, `report`, or retained runtime internals.

Deletion must not remove shared runtime components that still serve the retained paths, even if they are not themselves public commands.

## Error Handling And Edge Cases

- Missing input source: `run` fails with a message requiring one of `--goal`, `--case-yaml`, or `--case-dir`.
- Multiple input sources: `run` fails before loading config-heavy runtime state.
- `--strict --goal`: fail because strict-core requires authored YAML steps.
- Dynamic `--case-yaml` unreadable file: fail with a file-read configuration error.
- Dynamic `--case-yaml` invalid YAML: do not fail because the LLM path does not parse YAML.
- Strict `--case-yaml` invalid YAML: fail before execution through existing FSQ loader validation.
- Empty `--case-dir`: fail with a concise no-cases-found error.
- Directory run with some failed cases: continue through remaining cases; final exit status reflects aggregate failure.
- Strict case contains `assertWithAI`: fail clearly because strict mode has no LLM participation.
- Report run id not found: list checked report paths.
- Report run id ambiguous: fail rather than guessing.

## Affected Specs Expected To Change

- `SPEC.md`: Update module table language if needed to reflect the converged public behavior.
- `fsq_agent/cli/SPEC.md`: Replace current command list with `init`, `run`, `report`; define `run --strict`; define input source rules.
- `fsq_agent/agent/SPEC.md`: Remove standalone public pre-plan behavior; define dynamic goal/reference execution as the only LLM CLI path.
- `fsq_agent/fsq/SPEC.md`: Remove parsed-FSQ-to-agent-task behavior from the public path; keep strict parsing and executable-step conversion.
- `fsq_agent/core/SPEC.md`: Confirm strict-core remains deterministic and LLM-free through `run --strict`.
- `fsq_agent/config/SPEC.md`: Define strict-mode config requirements and `init` readiness checks.
- `fsq_agent/report/SPEC.md`: Define report lookup across `report.*` and `core-report.*`.
- `fsq_agent/models/SPEC.md`: Remove or narrow public model exports only where usage analysis proves they no longer support retained behavior.

## Verification Expectations

After SPEC updates and implementation, verification should include:

- CLI command discovery test proving only `init`, `run`, and `report` are registered.
- CLI input validation tests for mutually exclusive sources, missing source, and `--strict --goal` rejection.
- Dynamic `--goal` test proving one `Task` is created and sent through `FsqAgent.run`.
- Dynamic `--case-yaml` test proving raw file text is included and `FsqCaseLoader`/`FsqTaskAdapter` are not called.
- Dynamic `--case-dir` test proving files are discovered, sorted, and run serially as raw text tasks.
- Strict `--case-yaml` test proving config-based Android settings are used and no OpenAI validation/evaluator is constructed.
- Strict `--case-dir` test proving serial execution continues after failures and returns aggregate failure.
- Strict `assertWithAI` test proving no LLM is invoked and the failure is explicit.
- `init` tests for static config validation and separate LLM/strict readiness reporting.
- `report` tests for LLM report lookup, strict-core report lookup, missing report error, and ambiguity error.
- Import/reference tests or static search checks confirming deleted command helpers and `FsqTaskAdapter` are no longer reachable.
- Existing core runner, FSQ executable-step adapter, report generator, and agent runtime tests updated only where their public contract changed.
- Independent diff-based SPEC implementation audit before completion is claimed.

## Resolved Questions

- Public commands should be `init`, `run`, and `report`.
- `init` should combine initialization with config/readiness checks.
- Normal `run` is the LLM dynamic goal path; no separate agent mode flag is needed.
- Dynamic inputs are `--goal`, `--case-yaml`, and `--case-dir`.
- Inline YAML content is not supported.
- Dynamic YAML file input is read as complete raw text and is not parsed.
- Strict execution is selected with `--strict` on `run`.
- Strict execution reads Android device/app settings from config rather than CLI options.
- `report` should support LLM reports today and should be extended to support strict-core reports automatically.

## Handoff

This design document is not the implementation source of truth. The next step is to use the spec-driven workflow to translate this design into root and module `SPEC.md` updates, review those SPEC changes, and only then implement code against the confirmed specs.
