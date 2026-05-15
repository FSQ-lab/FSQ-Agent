# Module: fsq

## Purpose

Load FSQ AI Test DSL YAML cases from the merged FSQ testcase repository and convert them into goal-driven agent tasks. FSQ YAML is treated as structured reference context: case metadata, intended flow, locator hints, and assertions guide the OpenAI Agents SDK loop, but the agent may adapt the flow to live UI state. Required concrete commands are distilled into complete ordered key actions for execution and structured verification criteria for final judgment.

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
- `_task_adapter.py`: Renders FSQ metadata, inferred preconditions, and commands into an advisory task description for the agent loop, extracts required ordered key actions, and classifies them as structured verification criteria.
- `SPEC.md`: Module design.

## Error Handling

Invalid FSQ YAML raises `ConfigurationError` with the failing path. Missing command documents, unsupported schema versions, missing platform values, and malformed command lists are rejected before agent execution starts.

## Design Decisions

- `.codex.yaml` is the canonical test case input format.
- Configured `cases.dir` is treated as read-only input. Task execution may read FSQ case files from it, but generated files and evidence must be written under the output root.
- Markdown conversion reports are intentionally ignored and are not loaded as task inputs.
- FSQ commands are reference flow hints rather than a mandatory deterministic script.
- Required executable and assertion commands are extracted as ordered key actions. The execution agent always receives the full ordered key-action list regardless of final verification mode. Key actions represent the goal's necessary path and must be attempted in the same relative order, but transient dialogs, waits, screenshots, diagnostics, and recovery steps may be inserted between them.
- Required ordered key actions are also classified into final verification criteria. Assertion commands such as `assert`, `assertVisible`, and `assertWithAI` are `assertion` criteria. Operation commands such as taps, typing, key presses, scrolls, swipes, waits, and navigation are `operation` criteria. The case goal is represented as a `goal` criterion.
- `assertWithAI` commands are preserved as required ordered visual assertions when not optional. FSQ does not evaluate the image itself; it carries the assertion prompt into the task so the agent can collect screenshot evidence and the verification layer can judge the visual claim.
- `launchApp` and `killApp` are treated as setup and teardown intent, not as core goal key actions.
- Commands marked `optional: true` are preserved in the reference flow but are not required key actions or final verification criteria.
- If a case has no required key actions, the case name is still represented as the goal-level criterion.
- Locators and assertions are preserved in the rendered task description so the agent can prefer them while still handling optional dialogs, missing setup, or extra recovery steps.
- Case metadata, tags, description text, and command targets are scanned for AI-friendly precondition signals such as `requires-*`, `already signed in`, `MSA`, `login`, `account`, or similar setup language. Inferred preconditions are rendered as setup obligations before ordered key actions: the agent must inspect live state first, complete the prerequisite only when it is not already satisfied, and then continue with the case flow.
- Account-dependent FSQ cases may reference secret environment variable names such as `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD`, but the adapter must never embed credential values in task descriptions, key actions, or verification criteria.
