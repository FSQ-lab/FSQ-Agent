# Module: cli

## Purpose

Provide command line entry points for validating OpenAI Agents SDK configuration, running individual tasks, running batches, listing capabilities, and generating reports from prior runs.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, and shared exceptions.
- `config`: Loads settings.
- `agent`: Runs task workflows.
- `tools`: Lists available capabilities.
- `report`: Regenerates reports from stored run data when requested.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `main`: CLI entry point for package scripts.

Current commands:

- `auto-test-agent validate-config --config PATH`: Validate Azure OpenAI, OpenAI Agents SDK, MCP, shell, skills, CLI, and output settings without running a task.
- `auto-test-agent run --task PATH`: Run one YAML or JSON task file through the OpenAI Agents SDK runtime.
- `auto-test-agent run-batch --tasks PATH --parallel N`: Run a directory of task files with bounded concurrency.
- `auto-test-agent capabilities`: Print discovered MCP, CLI, and file operation capabilities.
- `auto-test-agent report --run-id ID --format FORMAT`: Regenerate a report for a previous run.

## Internal Structure

- `__init__.py`: Public exports only.
- `__main__.py`: Package entry point for `python -m auto_test_agent.cli` and VS Code launch configurations.
- `_main.py`: Click command group and command handlers.
- `_task_loader.py`: Task YAML and JSON file loading.
- `_formatting.py`: Rich console rendering helpers.
- `SPEC.md`: Module design.

## Error Handling

CLI commands catch `AutoTestAgentError` subclasses from `models`, render concise user-facing messages, and exit nonzero. Unexpected exceptions are logged with trace details and summarized in the console.

## Design Decisions

- CLI commands are thin adapters over module APIs, not a second orchestration layer.
- Task input supports YAML and JSON for CI friendliness and human editing. A task file may contain only `description`; `id`, `name`, and `acceptance_criteria` are optional, and acceptance criteria can be derived by the runtime.
- Batch execution uses bounded concurrency and creates independent agent runtime state per task so SDK sessions, MCP connections, and tool approvals do not leak across tasks.
- CLI output never prints API key values; it may print the configured API key environment variable name and whether it is present.
