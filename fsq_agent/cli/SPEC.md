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

- `auto-test-agent validate-config --config PATH`: Validate Azure OpenAI, OpenAI Agents SDK, MCP, shell, skills, CLI, and output settings without running a task.
- `auto-test-agent run --task PATH`: Run one `.codex.yaml` FSQ case through the OpenAI Agents SDK runtime.
- `auto-test-agent run-batch --tasks PATH --parallel N`: Run a directory tree of `.codex.yaml` FSQ cases with bounded concurrency.
- `auto-test-agent capabilities`: Print discovered MCP, CLI, and file operation capabilities.
- `auto-test-agent report --run-id ID --format FORMAT`: Regenerate a report for a previous run.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m fsq_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_task_loader.py`: FSQ `.codex.yaml` loading and conversion to agent tasks.
- `_formatting.py`: Rich console rendering helpers.
- `SPEC.md`: Module design.

## Error Handling

CLI commands catch `AutoTestAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- FSQ `.codex.yaml` is the primary case input. The loader treats FSQ command flow as structured reference context and lets the OpenAI Agents SDK runtime derive success criteria from the case description, assertions, locators, knowledge, and skills.
- Batch execution uses bounded concurrency and creates independent agent runtime state per task so SDK sessions, MCP connections, and tool approvals do not leak across tasks.
- CLI output never prints API key values; it may print the configured API key environment variable name and whether it is present.
