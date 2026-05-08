# Module: fsq

## Purpose

Load FSQ AI Test DSL YAML cases from the merged FSQ testcase repository and convert them into goal-driven agent tasks. FSQ YAML is treated as structured reference context: case metadata, intended flow, locator hints, and assertions guide the OpenAI Agents SDK loop, but the agent may adapt the flow to live UI state.

## Dependencies

- `models`: Uses `FsqCase`, `FsqCaseConfig`, `Task`, and shared configuration errors.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `FsqCaseLoader`: Loads two-document `.codex.yaml` FSQ cases.
- `FsqTaskAdapter`: Converts an `FsqCase` into the project `Task` model.
- `is_fsq_case_file`: Detects FSQ case file names.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML parsing, validation of FSQ document shape, and batch discovery.
- `_task_adapter.py`: Renders FSQ metadata and commands into an advisory task description for the agent loop.
- `SPEC.md`: Module design.

## Error Handling

Invalid FSQ YAML raises `ConfigurationError` with the failing path. Missing command documents, unsupported schema versions, missing platform values, and malformed command lists are rejected before agent execution starts.

## Design Decisions

- `.codex.yaml` is the canonical test case input format.
- Markdown conversion reports are intentionally ignored and are not loaded as task inputs.
- FSQ commands are reference flow hints rather than a mandatory deterministic script.
- Locators and assertions are preserved in the rendered task description so the agent can prefer them while still handling optional dialogs, missing setup, or extra recovery steps.
