# Module: cli

## Purpose

Provide the public command line surface for fsq-agent: initialize/check runtime readiness, run either dynamic LLM goal/reference execution or strict-core YAML execution with optional explicit provider-backed `assertWithAI`, optionally record dynamic LLM runs into strict-replay FSQ YAML artifacts, and print stored reports from prior runs.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, FSQ case models, strict replay refs, wait parameter models, report artifacts, and shared exceptions.
- `config`: Loads settings and validates LLM or strict-core readiness.
- `providers`: Builds shared provider sessions and AI assertion evaluators for dynamic runs and strict runs that contain explicit `assertWithAI` steps.
- `core`: Composes deterministic `ExecutableStep` execution, pure waits, runner events, and evidence manifest writing at the entry boundary.
- `fsq`: Loads `.codex.yaml` FSQ cases and converts parsed cases into strict-core executable steps.
- `agent`: Runs dynamic LLM goal/reference task workflows and persists recordable safe event metadata.
- `report`: Generates strict-core reports and resolves stored LLM or strict-core reports by run id.
- `tools`: Provides `get_runtime_secret` and `wait_ms` CommonTool event metadata that dynamic recording may convert into replayable strict YAML dependencies.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `main`: CLI entry point for package scripts.

Current commands:

- `fsq-agent init --config PATH --workspace PATH`: Initialize or verify the fsq-agent workspace, validate static configuration, and print readiness for the default LLM run path, strict-core run path, and provider-backed AI assertion readiness. Static configuration or workspace failures exit nonzero. Mode-specific dependency gaps are reported as readiness failures so strict-only users are not forced to configure LLM credentials unless they execute cases containing `assertWithAI`.
- `fsq-agent run --goal TEXT --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl --record --record-on-failure`: Run one dynamic LLM task from a natural-language goal. This is the default run mode. Streaming is enabled by default for LLM run events. `--record` optionally records a strict-replay `.codex.yaml` artifact under the completed run directory when the final status is `success`; `--record-on-failure` permits draft recording for `failed` or `inconclusive` runs and is valid only with `--record`.
- `fsq-agent run --case-yaml PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl --record --record-on-failure`: In default mode, read the file as complete UTF-8 text and run one dynamic LLM task using that raw content as reference material. The CLI must not parse the input YAML for execution, normalize FSQ commands, extract key actions, or derive local operation/assertion criteria for this path. If `--record` is enabled, post-run recording may parse only the persisted event log and write a generated `recorded.codex.yaml` under the run directory.
- `fsq-agent run --case-dir PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl --record --record-on-failure`: In default mode, discover `*.codex.yaml` files recursively, sort them, read each file as complete UTF-8 text, and run one dynamic LLM task per file serially. Execution continues after failed cases and prints a final operational summary. When recording is enabled, each case run independently attempts to write `recorded.codex.yaml` and `recording.json`; recording failures do not stop later dynamic cases.
- `fsq-agent run --strict --case-yaml PATH --config PATH --workspace PATH`: Run one `.codex.yaml` FSQ case through the strict-core path. The case is parsed and converted into `ExecutableStep` records, strict replay refs such as `{runtimeSecret: NAME}` are validated and resolved in memory before external UI actions begin, and steps are executed through `StepSequenceRunner` with the configured Android harness/driver. The run writes `evidence-manifest.json`, generates `core-report.md/json`, and prints generated paths. Locator fallback, action repair, recovery, testcase mutation, and strict-mode recording are not allowed. If the parsed case contains an explicitly authored `assertWithAI` step, CLI validates provider readiness, builds a provider-backed AI assertion evaluator through `providers`, and injects it into `AndroidHarness` before execution.
- `fsq-agent run --strict --case-dir PATH --config PATH --workspace PATH`: Run discovered `*.codex.yaml` files serially through the same deterministic strict-core path. Execution continues after failed cases, writes a directory-run summary, and exits nonzero when any case fails.
- `fsq-agent report --run-id ID --format markdown|json --config PATH --workspace PATH`: Print a stored report from the configured runs directory. The command resolves either `report.md/json` for LLM runs or `core-report.md/json` for strict-core runs and fails when no matching report exists or when the run id is ambiguous.

`--goal`, `--case-yaml`, and `--case-dir` are mutually exclusive. `--strict --goal` is invalid because strict-core execution requires authored YAML steps. `--strict --record` and `--strict --record-on-failure` are invalid because recording is a dynamic-run post-processing workflow. `--record-on-failure` without `--record` is invalid. Relative case paths resolve against `cases.dir` first, then the current working directory.

Dynamic recording writes the following run-local files when attempted:

```text
<runs_dir>/<run-id>/
    recorded.codex.yaml
    recording.json
```

`recorded.codex.yaml` contains two YAML documents: generated FSQ metadata followed by recorded commands. Generated metadata must include `tags` identifying the case as recorded and `properties.recording` with source run id, source task id, source status, `draft`, required runtime secret names, and warnings. `recording.json` contains recording status, command count, recorded case path when present, required runtime secret names, warnings, skipped tool calls, validation status, and errors when recording fails. Neither file may contain secret values.

The recording helper reconstructs logical tool calls from the dynamic run's `events.jsonl`. Harness-origin calls with safe `fsq_action_name` provenance become FSQ commands when their arguments validate and their structured harness status indicates success. Version 1 records only two CommonTools as replayable dependencies: `get_runtime_secret` and `wait_ms`. `get_runtime_secret` is recorded only as a runtime-secret name dependency that may replace redacted harness argument fields with `{runtimeSecret: NAME}`; `wait_ms` becomes a pure `waitMs` command in the recorded YAML. Other CommonTools are diagnostics and are not replayed.

Strict replay reference resolution is an entry-layer responsibility. Before passing steps to `StepSequenceRunner`, CLI validates every referenced runtime secret name against `runtime_secrets.allowed_env_names`, verifies the corresponding environment value exists, substitutes secret values into step params only in memory, and redacts any resolved secret values from persisted events, manifests, reports, and logging.

Internal deterministic-core composition helper:

```python
bundle = run_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
)
```

This helper is not a public CLI command. It exists to give `run --strict` and tests a single entry-layer path for running one FSQ case through the deterministic core. It should load the FSQ case, convert commands to `ExecutableStep` records, run them through `StepSequenceRunner` with the caller-supplied harness, write `evidence-manifest.json`, and return an `EvidenceBundle` whose `manifest_path` points to the written manifest.

The helper must not construct real platform drivers, choose Android backend settings, or add retry/report policy. Those remain future entry-layer responsibilities after the core execution contract is stable.

Internal strict deterministic-core entry:

```python
artifact = run_strict_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
)
```

This strict entry executes the YAML exactly as authored with the supplied harness, writes `evidence-manifest.json`, generates `core-report.md` and `core-report.json`, and returns the generated Markdown `ReportArtifact`. It must not enable locator fallback, AI recovery, testcase mutation, platform-driver construction, OpenAI provider validation, or AI assertion evaluator construction. If AI assertion is needed, the caller must provide a harness that already has an evaluator injected. Recovery execution should use a separate future entry so strict results remain auditable.

Internal dynamic recording helper:

```python
recording = record_dynamic_run_as_strict_case(
    run_dir=Path("runs/run-1"),
    task=task,
    result=result,
    settings=settings,
    allow_failure=False,
)
```

This helper is not a public CLI command. It reads a completed dynamic run directory, writes `recorded.codex.yaml` and `recording.json` when eligible and replayable, validates generated YAML through `fsq`, and returns an internal recording summary used for CLI output and directory-run summaries. It must not call provider APIs, execute platform actions, mutate source case files, or reveal secret values.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_task_loader.py`: Raw goal-source loading for LLM runs and path discovery/resolution for both run modes.
- `_core_execution.py`: Internal composition helper for deterministic FSQ case execution through `core` with a caller-supplied harness.
- `_strict_case_recording.py`: Internal post-run recorder that converts dynamic run events into run-local `recorded.codex.yaml` and `recording.json` artifacts.
- `_strict_replay.py`: Internal strict-entry helper that validates and resolves strict replay refs, including runtime-secret refs, before deterministic core execution.
- `_formatting.py`: Logging-backed CLI rendering helpers for task results, live events, strict run summaries, and report paths.
- `_logging.py`: CLI logging configuration.
- `SPEC.md`: Module design.

## Error Handling

CLI commands catch `FsqAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

Input validation failures, including missing input source, multiple input sources, `--strict --goal`, invalid record flag combinations, unreadable dynamic case files, invalid strict YAML, empty case directories, missing strict app id, missing strict replay secret allowlist/presence, missing provider readiness for authored strict `assertWithAI`, or unresolved reports must fail before external UI actions begin. Dynamic `--case-yaml` input must not fail merely because the file is invalid YAML, because that path does not parse YAML.

Recording failures happen after a dynamic run and must not change that dynamic run's status. The CLI should log and summarize recording errors, including no replayable commands, ambiguous secret binding, redacted values with no matching runtime secret, unsupported replay commands, generated YAML validation failures, and existing `recorded.codex.yaml` conflicts. Directory runs continue after per-case recording failures.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- The public command surface is intentionally limited to `init`, `run`, and `report`. Deleted command names are not retained as compatibility aliases.
- Streaming CLI output logs live `RunEvent` values from the agent. Rich format is optimized for humans and includes `HH:MM:SS LEVEL` log prefixes so operators can distinguish informational, warning, and error events. JSONL format emits one raw serialized event per log message for CI and log processors; the CLI formatter bypasses prefixes for those raw JSONL records so the stream remains machine-readable.
- Normal `run` is always dynamic LLM goal/reference execution. `--goal` supplies the goal directly. `--case-yaml` and `--case-dir` supply raw file content as reference material and must not use `FsqCaseLoader` or `FsqTaskAdapter`.
- Dynamic run recording is post-run evidence transformation, not task execution. It reads persisted run events after `FsqAgent.run` returns and writes only under that run directory.
- Recorded cases reflect actual successfully completed replayable harness actions plus supported replayable CommonTool dependencies. The recorder must not invent setup, teardown, assertions, locator fallback, recovery actions, or source YAML mutations. Missing assertions or lifecycle actions produce warnings.
- Runtime secrets in recorded cases are represented by environment variable names through `runtimeSecret` refs. Secret values are resolved only in memory during strict replay and are never written to generated YAML, event previews, manifests, reports, recording manifests, or logs.
- `run --strict` is strict-core execution. It parses FSQ YAML, uses config-owned Android settings, and does not construct or invoke LLM components for planning, recovery, locator fallback, action repair, or final verification. The sole provider-backed exception is an explicitly authored `assertWithAI` step, for which CLI may build and inject an AI assertion evaluator before execution.
- Directory execution is intentionally serial because UI automation cases share external device and application state. Each case still creates independent run state so SDK sessions, harness context, and CommonTool state do not leak across cases.
- `report` is a lookup/print command only; report generation happens during execution. It resolves either LLM reports or strict-core reports without exposing separate report commands.
- CLI logging never emits API key values; it may log the configured API key environment variable name and whether it is present.
