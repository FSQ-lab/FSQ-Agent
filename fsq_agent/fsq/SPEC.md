# Module: fsq

## Purpose

Load FSQ AI Test DSL YAML cases from the merged FSQ testcase repository and convert them into goal-driven agent tasks or deterministic execution-core steps. FSQ YAML is treated as structured reference context for agent tasks, and as the source of ordered `ExecutableStep` records for the core runner path. Goal-only FSQ cases may omit the command document or provide an empty command list; those cases use the case name as the goal and produce no adapter-owned executable steps.

## Dependencies

- `models`: Uses `FsqCase`, `FsqCaseConfig`, `Task`, shared configuration errors, execution-core contracts such as `ExecutableStep`, `SourceRef`, and `EvidencePolicy`, and the shared Android action registry for deterministic Android command payload normalization and step kind classification.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `FsqCaseLoader`: Loads `.codex.yaml` FSQ cases from explicit paths or the configured read-only case directory. It accepts traditional metadata-plus-command cases and goal-only metadata cases.
- `FsqTaskAdapter`: Converts an `FsqCase` into the project `Task` model.
- `FsqExecutableStepAdapter`: Converts an `FsqCase` command document into ordered `ExecutableStep` records for deterministic core execution.
- `is_fsq_case_file`: Detects FSQ case file names.

The first deterministic step adapter exposes a narrow API:

```python
adapter = FsqExecutableStepAdapter()
steps = adapter.to_executable_steps(case)
```

`FsqExecutableStepAdapter` preserves FSQ action names exactly in `ExecutableStep.action_name`, including names such as `tapOn`, `inputText`, `pressKey`, `assertVisible`, `assert`, and `performActions`. It should not translate action names into platform driver method names; platform harnesses own that mapping.

The adapter should normalize each known Android YAML command into `ExecutableStep.params` by looking up the action in `ANDROID_ACTION_DEFINITIONS_BY_NAME`, validating object-shaped payloads against the registry's shared parameter model, then storing `model_dump(mode="json", exclude_none=True)`. Known Android action payloads should be authored in the same field shape as their parameter models rather than relying on action-specific scalar shorthand. The first-batch canonical forms are:

| FSQ command shape | `action_name` | `params` |
|---|---|---|
| `launchApp` | `launchApp` | `{}` |
| `killApp` | `killApp` | `{}` |
| `pressKey: {key: Enter}` | `pressKey` | `{"key": "Enter"}` |
| `tapOn: {target: Login}` | `tapOn` | `{"target": "Login"}` |
| `performActions: {actions: [...]}` | `performActions` | `{"actions": [...]}` |
| `inputText: {text: bing.com, ...}` | `inputText` | validated `AndroidInputTextParams` dump |
| `assertVisible: {...}` | `assertVisible` | validated `AndroidAssertVisibleParams` dump |
| `assertNotVisible: {...}` | `assertNotVisible` | validated `AndroidAssertNotVisibleParams` dump |
| `longPressOn: {...}` | `longPressOn` | validated `AndroidLongPressOnParams` dump |
| `swipe: {...}` | `swipe` | validated `AndroidSwipeParams` dump |
| `assert: {element: ..., text: ...}` | `assert` | validated `AndroidAssertStateParams` dump |
| `assertWithAI: {prompt: ...}` | `assertWithAI` | validated `AndroidAssertWithAIParams` dump |

Runner-owned metadata such as valid `timeout` values should be extracted before driver parameter validation and stored in `ExecutableStep.timeout_ms`, not passed through to driver parameter models. The original raw command remains available in `ExecutableStep.metadata` for evidence and debugging.

The first-batch step kind mapping for known Android actions is owned by the same Android action registry:

| FSQ action | `ExecutableStep.kind` |
|---|---|
| `launchApp` | `setup` |
| `killApp` | `teardown` |
| `assert`, `assertVisible`, `assertNotVisible`, `assertWithAI` | `assertion` |
| `takeScreenshot`, `startRecording`, `stopRecording` | `observation` |
| all other commands | `action` |

Each generated step should include:

- `step_id`: stable within the case, using the case id and one-based command index, for example `fundamental_test_bing_com_website-step-001`.
- `source_ref`: `source_type="fsq"`, `source_id` set to the case path string, `step_index` set to the zero-based command index, and metadata containing the case name and platform.
- `metadata`: the original command payload and selected case metadata useful for evidence and debugging.
- `timeout_ms`: copied from command object `timeout` when present and valid.
- `evidence_policy`: default shared model policy for now. Rich FSQ evidence controls are a later batch.

Malformed command entries that cannot be reduced to one FSQ action must raise `ConfigurationError` with the case path and command index. Known Android command payloads that fail shared parameter model validation, including legacy scalar shorthand such as `pressKey: Enter` or `performActions: [...]`, must also raise `ConfigurationError` before execution starts, with enough context to identify the case path, command index, action name, and validation problem. Optional commands are still converted into executable steps; optional/non-blocking execution semantics belong to the core runner or a later policy layer, not this adapter.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML parsing, validation of FSQ document shape, goal-only case normalization, and batch discovery.
- `_task_adapter.py`: Renders FSQ metadata, inferred preconditions, and commands into an advisory task description for the agent loop, extracts required ordered key actions, and classifies them as structured verification criteria.
- `_step_adapter.py`: Converts loaded FSQ commands into ordered `ExecutableStep` records for deterministic core execution.
- `SPEC.md`: Module design.

## Error Handling

Invalid FSQ YAML raises `ConfigurationError` with the failing path. Unsupported schema versions, missing platform values, and malformed command documents are rejected before agent execution starts. A missing command document or empty command list is valid only as a goal-only case and is normalized to `commands=[]`.

## Design Decisions

- `.codex.yaml` is the canonical test case input format.
- Single-document `.codex.yaml` files containing only valid case metadata are supported as goal-only cases. Two-document cases with `[]` or an otherwise empty command list are also goal-only cases.
- Configured `cases.dir` is treated as read-only input. Task execution may read FSQ case files from it, but generated files and evidence must be written under the output root.
- Markdown conversion reports are intentionally ignored and are not loaded as task inputs.
- FSQ commands are reference flow hints for agent tasks, and deterministic ordered input for the core execution path when converted by `FsqExecutableStepAdapter`.
- Deterministic Android command payload normalization uses the shared Android action registry from `models`. Authored Android command payloads use the same object field names as the registry's parameter models, which keeps case parsing, future case generation, harness dispatch, and function-call schemas aligned to one payload contract while preserving FSQ action names in `ExecutableStep.action_name`.
- Required executable and assertion commands are extracted as ordered key actions. The execution agent always receives the full ordered key-action list regardless of final verification mode. Key actions represent the goal's necessary path and must be attempted in the same relative order, but transient dialogs, waits, screenshots, diagnostics, and recovery steps may be inserted between them.
- Required ordered key actions are also classified into final verification criteria. Assertion commands such as `assert`, `assertVisible`, and `assertWithAI` are `assertion` criteria. Operation commands such as taps, typing, key presses, scrolls, swipes, waits, and navigation are `operation` criteria. The case goal is represented as a `goal` criterion.
- `assertWithAI` commands are preserved as required ordered visual assertions when not optional. FSQ does not evaluate the image itself; it carries the assertion prompt into the task so the agent can collect screenshot evidence and the verification layer can judge the visual claim.
- `launchApp` and `killApp` are treated as setup and teardown intent, not as core goal key actions.
- Commands marked `optional: true` are preserved in the reference flow but are not required key actions or final verification criteria.
- If a case has no required key actions, the case name is still represented as the goal-level criterion.
- Goal-only cases intentionally produce no adapter-owned ordered key actions and only a goal-level final verification criterion. Generated key actions from runtime pre-planning are execution guidance and must not be added as blocking final-verification criteria by the FSQ adapter.
- Locators and assertions are preserved in the rendered task description so the agent can prefer them while still handling optional dialogs, missing setup, or extra recovery steps.
- Case metadata, tags, description text, and command targets are scanned for AI-friendly precondition signals such as `requires-*`, `already signed in`, `MSA`, `login`, `account`, or similar setup language. Inferred preconditions are rendered as setup obligations before ordered key actions: the agent must inspect live state first, complete the prerequisite only when it is not already satisfied, and then continue with the case flow.
- Account-dependent FSQ cases may reference secret environment variable names such as `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD`, but the adapter must never embed credential values in task descriptions, key actions, or verification criteria.
- `FsqExecutableStepAdapter` must not import or call `core`; it produces shared model contracts only. Higher-level entry code is responsible for passing those steps into core runners.
