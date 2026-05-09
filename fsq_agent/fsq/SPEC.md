# Module: fsq

## Purpose

Load FSQ AI Test DSL YAML cases from the merged FSQ testcase repository and convert them into goal-driven agent tasks. FSQ YAML is treated as structured reference context: case metadata, intended flow, locator hints, and assertions guide the OpenAI Agents SDK loop, but the agent may adapt the flow to live UI state. Required concrete commands are also distilled into ordered key actions that act as the task's acceptance spine.

## Dependencies

- `models`: Uses `FsqCase`, `FsqCaseConfig`, `Task`, and shared configuration errors.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `FsqCaseLoader`: Loads two-document `.codex.yaml` FSQ cases from explicit paths or the configured read-only case directory.
- `FsqTaskAdapter`: Converts an `FsqCase` into the project `Task` model.
- `is_fsq_case_file`: Detects FSQ case file names.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML parsing, validation of FSQ document shape, and batch discovery.
- `_task_adapter.py`: Renders FSQ metadata and commands into an advisory task description for the agent loop, extracts required ordered key actions, and maps them to task acceptance criteria.
- `SPEC.md`: Module design.

## Error Handling

Invalid FSQ YAML raises `ConfigurationError` with the failing path. Missing command documents, unsupported schema versions, missing platform values, and malformed command lists are rejected before agent execution starts.

## Design Decisions

- `.codex.yaml` is the canonical test case input format.
- Configured `cases.dir` is treated as read-only input. Task execution may read FSQ case files from it, but generated files and evidence must be written under the output root.
- Markdown conversion reports are intentionally ignored and are not loaded as task inputs.
- FSQ commands are reference flow hints rather than a mandatory deterministic script.
- Required executable and assertion commands are extracted as ordered key actions. Key actions represent the goal's necessary path and must be satisfied in the same relative order, but transient dialogs, waits, screenshots, diagnostics, and recovery steps may be inserted between them.
- `launchApp` and `killApp` are treated as setup and teardown intent, not as core goal key actions.
- Commands marked `optional: true` are preserved in the reference flow but are not required acceptance criteria.
- If a case has no required key actions, the case name is used as the goal-level acceptance criterion.
- Locators and assertions are preserved in the rendered task description so the agent can prefer them while still handling optional dialogs, missing setup, or extra recovery steps.
