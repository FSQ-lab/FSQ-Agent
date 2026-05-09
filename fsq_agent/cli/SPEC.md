# Module: cli

## Purpose

Provide command line entry points for validating OpenAI Agents SDK configuration, running individual FSQ YAML-guided tasks, running batches, listing capabilities, and generating reports from prior runs.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, FSQ case models, and shared exceptions.
- `config`: Loads settings.
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
- `fsq-agent run --task PATH --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: Run one `.codex.yaml` FSQ case through the OpenAI Agents SDK runtime. Relative task paths resolve against `cases.dir` first. Streaming is enabled by default.
- `fsq-agent run-batch --tasks PATH --parallel N --config PATH --workspace PATH --stream/--no-stream --stream-format rich|jsonl`: Run a directory tree of `.codex.yaml` FSQ cases with bounded concurrency. If `--tasks` is omitted, the command scans `cases.dir`.
- `fsq-agent capabilities --config PATH --workspace PATH`: Print discovered MCP, CLI, and file operation capabilities.
- `fsq-agent report --run-id ID --format FORMAT --config PATH --workspace PATH`: Print a report from the configured workspace output runs directory.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_task_loader.py`: FSQ `.codex.yaml` loading and conversion to agent tasks.
- `_formatting.py`: Rich console rendering helpers.
- `SPEC.md`: Module design.

## Error Handling

CLI commands catch `FsqAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- Streaming CLI output renders live `RunEvent` values from the agent. Rich format is optimized for humans; JSONL format emits one serialized event per line for CI and log processors.
- FSQ `.codex.yaml` is the primary case input. The loader treats FSQ command flow as structured reference context and lets the OpenAI Agents SDK runtime derive success criteria from the case description, assertions, locators, knowledge, and skills.
- Batch execution uses bounded concurrency and creates independent agent runtime state per task so SDK sessions, MCP connections, and tool approvals do not leak across tasks.
- CLI output never prints API key values; it may print the configured API key environment variable name and whether it is present.
