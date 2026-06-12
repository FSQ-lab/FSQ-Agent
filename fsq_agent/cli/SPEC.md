# Module: cli

## Purpose

Provide the public command line surface for fsq-agent: initialize/check runtime readiness, run either dynamic LLM goal/reference execution or strict-core YAML execution with optional explicit provider-backed `assertWithAI`, and print stored reports from prior runs.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, FSQ case models, report artifacts, and shared exceptions.
- `config`: Loads settings and validates LLM or strict-core readiness.
- `providers`: Builds shared provider sessions and AI assertion evaluators for dynamic runs and strict runs that contain explicit `assertWithAI` steps.
- `core`: Composes deterministic `ExecutableStep` execution, runner events, and evidence manifest writing at the entry boundary.
- `fsq`: Loads `.codex.yaml` FSQ cases and converts parsed cases into strict-core executable steps.
- `agent`: Runs dynamic LLM goal/reference task workflows.
- `report`: Generates strict-core reports and resolves stored LLM or strict-core reports by run id.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `main`: CLI entry point for package scripts.

Current commands:

- `fsq-agent init --config PATH --workspace PATH`: Initialize or verify the fsq-agent workspace, validate static configuration, and print readiness for the default LLM run path, strict-core run path, and provider-backed AI assertion readiness. Static configuration or workspace failures exit nonzero. Mode-specific dependency gaps are reported as readiness failures so strict-only users are not forced to configure LLM credentials unless they execute cases containing `assertWithAI`.
- `fsq-agent run --goal TEXT --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: Run one dynamic LLM task from a natural-language goal. This is the default run mode. Streaming is enabled by default for LLM run events.
- `fsq-agent run --case-yaml PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: In default mode, read the file as complete UTF-8 text and run one dynamic LLM task using that raw content as reference material. The CLI must not parse the YAML, normalize FSQ commands, extract key actions, or derive local operation/assertion criteria for this path.
- `fsq-agent run --case-dir PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: In default mode, discover `*.codex.yaml` files recursively, sort them, read each file as complete UTF-8 text, and run one dynamic LLM task per file serially. Execution continues after failed cases and prints a final operational summary.
- `fsq-agent run --strict --case-yaml PATH --config PATH --workspace PATH`: Run one `.codex.yaml` FSQ case through the strict-core path. The case is parsed and converted into `ExecutableStep` records, executed through `StepSequenceRunner` with the configured Android harness/driver, writes `evidence-manifest.json`, generates `core-report.md/json`, and prints generated paths. Locator fallback, action repair, recovery, and testcase mutation are not allowed. If the parsed case contains an explicitly authored `assertWithAI` step, CLI validates provider readiness, builds a provider-backed AI assertion evaluator through `providers`, and injects it into `AndroidHarness` before execution.
- `fsq-agent run --strict --case-dir PATH --config PATH --workspace PATH`: Run discovered `*.codex.yaml` files serially through the same deterministic strict-core path. Execution continues after failed cases, writes a directory-run summary, and exits nonzero when any case fails.
- `fsq-agent report --run-id ID --format markdown|json --config PATH --workspace PATH`: Print a stored report from the configured runs directory. The command resolves either `report.md/json` for LLM runs or `core-report.md/json` for strict-core runs and fails when no matching report exists or when the run id is ambiguous.

`--goal`, `--case-yaml`, and `--case-dir` are mutually exclusive. `--strict --goal` is invalid because strict-core execution requires authored YAML steps. Relative case paths resolve against `cases.dir` first, then the current working directory.

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

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_task_loader.py`: Raw goal-source loading for LLM runs and path discovery/resolution for both run modes.
- `_core_execution.py`: Internal composition helper for deterministic FSQ case execution through `core` with a caller-supplied harness.
- `_formatting.py`: Logging-backed CLI rendering helpers for task results, live events, strict run summaries, and report paths.
- `_logging.py`: CLI logging configuration.
- `SPEC.md`: Module design.

## Error Handling

CLI commands catch `FsqAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

Input validation failures, including missing input source, multiple input sources, `--strict --goal`, unreadable dynamic case files, invalid strict YAML, empty case directories, missing strict app id, missing provider readiness for authored strict `assertWithAI`, or unresolved reports must fail before external UI actions begin. Dynamic `--case-yaml` input must not fail merely because the file is invalid YAML, because that path does not parse YAML.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- The public command surface is intentionally limited to `init`, `run`, and `report`. Deleted command names are not retained as compatibility aliases.
- Streaming CLI output logs live `RunEvent` values from the agent. Rich format is optimized for humans and includes `HH:MM:SS LEVEL` log prefixes so operators can distinguish informational, warning, and error events. JSONL format emits one raw serialized event per log message for CI and log processors; the CLI formatter bypasses prefixes for those raw JSONL records so the stream remains machine-readable.
- Normal `run` is always dynamic LLM goal/reference execution. `--goal` supplies the goal directly. `--case-yaml` and `--case-dir` supply raw file content as reference material and must not use `FsqCaseLoader` or `FsqTaskAdapter`.
- `run --strict` is strict-core execution. It parses FSQ YAML, uses config-owned Android settings, and does not construct or invoke LLM components for planning, recovery, locator fallback, action repair, or final verification. The sole provider-backed exception is an explicitly authored `assertWithAI` step, for which CLI may build and inject an AI assertion evaluator before execution.
- Directory execution is intentionally serial because UI automation cases share external device and application state. Each case still creates independent run state so SDK sessions, harness context, and CommonTool state do not leak across cases.
- `report` is a lookup/print command only; report generation happens during execution. It resolves either LLM reports or strict-core reports without exposing separate report commands.
- CLI logging never emits API key values; it may log the configured API key environment variable name and whether it is present.
