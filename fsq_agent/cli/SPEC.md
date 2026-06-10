# Module: cli

## Purpose

Provide command line entry points for validating OpenAI Agents SDK configuration, running individual FSQ YAML-guided tasks, running natural-language goal tasks, running batches, listing capabilities, and generating reports from prior runs.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, FSQ case models, and shared exceptions.
- `config`: Loads settings.
- `core`: Composes deterministic `ExecutableStep` execution, runner events, and evidence manifest writing at the entry boundary.
- `fsq`: Loads `.codex.yaml` FSQ cases and converts them into agent tasks.
- `agent`: Runs task workflows.
- `tools`: Lists available capabilities.
- `report`: Regenerates reports from stored run data when requested.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `main`: CLI entry point for package scripts.

Current commands:

- `fsq-agent init --config PATH --workspace PATH`: Initialize and mark the fsq-agent workspace.
- `fsq-agent validate-config --config PATH --workspace PATH`: Validate Azure OpenAI, OpenAI Agents SDK, MCP, shell, skills, CLI, workspace, cases, and output settings without running a task.
- `fsq-agent run --task PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: Run one `.codex.yaml` FSQ case through the OpenAI Agents SDK runtime. Relative task paths resolve against `cases.dir` first. Goal-only cases are supported and are pre-planned before execution. Streaming is enabled by default.
- `fsq-agent run-goal --goal TEXT --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: Run one natural-language goal task without a YAML case file. The goal is pre-planned into execution key actions before the normal runtime executes it, and final verification uses the goal-level criterion.
- `fsq-agent run-batch --tasks PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: Run a directory tree of `.codex.yaml` FSQ cases serially. If `--tasks` is omitted, the command scans `cases.dir`.
- `fsq-agent capabilities --config PATH --workspace PATH`: Print discovered MCP, CLI, and file operation capabilities.
- `fsq-agent report --run-id ID --format FORMAT --config PATH --workspace PATH`: Print a report from the configured workspace output runs directory.
- `fsq-agent pre-plan --goal TEXT --config PATH --workspace PATH --format text|json --stream/--no-stream --stream-format rich|jsonl`: Generate an ordered key-action pre-plan from a natural-language goal using configured page knowledge. This command does not execute UI actions or generate a run report.

Planned internal deterministic-core composition helper:

```python
bundle = run_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
)
```

This helper is not a public CLI command in the first batch. It exists to give future CLI commands and tests a single entry-layer path for running one FSQ case through the deterministic core. It should load the FSQ case, convert commands to `ExecutableStep` records, run them through `StepSequenceRunner` with the caller-supplied harness, write `evidence-manifest.json`, and return an `EvidenceBundle` whose `manifest_path` points to the written manifest.

The helper must not construct real platform drivers, choose Android backend settings, or add retry/report policy. Those remain future entry-layer responsibilities after the core execution contract is stable.

Planned internal strict deterministic-core entry:

```python
artifact = run_strict_fsq_core_case(
    case_path=Path("case.codex.yaml"),
    harness=harness,
    output_dir=Path("runs/run-1"),
    run_id="run-1",
)
```

This strict entry executes the YAML exactly as authored with the supplied harness, writes `evidence-manifest.json`, generates `core-report.md` and `core-report.json`, and returns the generated Markdown `ReportArtifact`. It must not enable locator fallback, AI recovery, testcase mutation, or platform-driver construction. Recovery execution should use a separate future entry so strict results remain auditable.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_task_loader.py`: FSQ `.codex.yaml` loading and conversion to agent tasks.
- `_core_execution.py`: Internal composition helper for deterministic FSQ case execution through `core` with a caller-supplied harness.
- `_pre_plan_formatting.py`: CLI rendering helpers for goal pre-plan text and JSON output.
- `_formatting.py`: Logging-backed CLI rendering helpers for task results, live events, and capability tables.
- `_logging.py`: CLI logging configuration.
- `SPEC.md`: Module design.

## Error Handling

CLI commands catch `FsqAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- Streaming CLI output logs live `RunEvent` values from the agent. Rich format is optimized for humans and includes `HH:MM:SS LEVEL` log prefixes so operators can distinguish informational, warning, and error events. JSONL format emits one raw serialized event per log message for CI and log processors; the CLI formatter bypasses prefixes for those raw JSONL records so the stream remains machine-readable.
- FSQ `.codex.yaml` is the primary case input. The loader treats FSQ command flow as structured reference context and lets the OpenAI Agents SDK runtime derive success criteria from the case description, assertions, locators, knowledge, and skills.
- `pre-plan` is the first standalone goal-planning entry point. It uses the configured knowledge directory and agent runtime to produce key actions, but deliberately stops before case execution, verification, and report generation.
- `run-goal` is the direct goal-task execution entry point. It creates a normal `Task` from the goal text and delegates to `FsqAgent.run`, so execution, verification, reporting, streaming, and errors remain consistent with `run --task`.
- Batch execution is intentionally serial because UI automation cases share external device and application state. Each task still creates independent agent runtime state so SDK sessions, MCP connections, and tool approvals do not leak across tasks.
- CLI logging never emits API key values; it may log the configured API key environment variable name and whether it is present.
