# Module: models

## Purpose

Own all shared data structures, configuration value models, result objects, tool metadata, skill metadata, report metadata, and exception classes used across fsq-agent. This module is the only place where cross-module types and custom exceptions are defined.

## Dependencies

No project module dependencies. May depend on external libraries such as `pydantic` and standard library typing modules.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `VerificationCriterion`: Pydantic model for one structured final-verification requirement. It includes criterion text, kind (`goal`, `assertion`, or `operation`), required flag, and source metadata.
- `Task`: Pydantic model describing a natural-language test task, optional metadata, complete execution key actions, structured final-verification criteria, retry limits, timeout, and knowledge references. Only `description` is required. Execution key actions are always available to the runner as planning context; final verification decides which criteria are blocking according to configured verification mode.
- `VerificationMode`: Literal policy value for final verification strictness: `strict`, `normal`, or `goal`.
- `AGENT_FINAL_OUTPUT_SCHEMA_VERSION`: Constant containing the current supported final-output schema version. The runtime supports only the current schema; future compatible schema evolution may add fields, while breaking changes replace the current schema rather than exposing a user-selectable schema configuration.
- `AgentTaskInput`: Pydantic model describing the structured task envelope rendered into the model input. It includes a schema version, the task, complete key actions for execution planning, structured verification criteria, optional runtime policy text, and the final output contract name expected for the run.
- `AgentPlanItem`: Pydantic model for one planned or adjusted agent step in final output.
- `AgentFinalOutput`: Pydantic model for the OpenAI Agents SDK structured final output contract. It contains schema version, task status, summary, pre-plan, plan updates, satisfied/unmet criteria, evidence, and errors.
- `ToolCallRecord`: Pydantic model for a normalized real tool invocation reconstructed from run events, including true tool name, origin, arguments, output preview, artifact reference, status, timing, and error fields.
- `FsqCaseConfig`: Pydantic model describing the metadata document from an FSQ AI Test DSL `.codex.yaml` case.
- `FsqCase`: Pydantic model containing an FSQ case path, parsed metadata, and command list.
- `ExecutionPlan`: Pydantic model containing ordered `ExecutionStep` items and planning rationale.
- `ExecutionStep`: Pydantic model for one planned tool action with expected outcome and retry policy.
- `StepResult`: Pydantic model for one executed, skipped, failed, or adjusted pre-plan step outcome, timings, evidence references, and error summary.
- `VerificationResult`: Pydantic model describing whether the task goal was achieved and why.
- `TaskResult`: Pydantic model returned by the agent after execution, verification, and report generation.
- `RunEvent`: Pydantic model for one live execution timeline event emitted during a task run, including run/task identity, sequence, timestamp, event type, title, message, optional tool call metadata, output preview, duration, and structured payload.
- `RunEventSink`: Callable type accepted by orchestration/runtime/tool code to receive `RunEvent` values synchronously or asynchronously.
- `ReportArtifact`: Pydantic model describing generated report paths and evidence bundle paths.
- `KnowledgeBundle`: Pydantic model containing loaded private knowledge and warnings for agent context.
- `PAGE_KNOWLEDGE_INDEX_SCHEMA_VERSION`: Constant containing the supported page-knowledge index schema version.
- `PAGE_KNOWLEDGE_PAGE_SCHEMA_VERSION`: Constant containing the supported page-knowledge page-node schema version.
- `GOAL_PRE_PLAN_SCHEMA_VERSION`: Constant containing the supported goal pre-plan schema version.
- `PageKnowledgeIndex`: Pydantic model for the public page-knowledge `index.md` JSON payload. It contains schema version, product, platform, page root, and concise page records used for fast goal-to-page lookup.
- `PageKnowledgeIndexEntry`: Pydantic model for one indexed page, including page id, relative file path, display name, and intent keywords.
- `PageKnowledgePage`: Pydantic model for one page graph node stored in `knowledge/pages/*.md`. It contains page id, name, semantic identifiers, optional images, and page elements.
- `PageIdentifier`: Pydantic model for one semantic page-recognition signal. It intentionally does not contain locators.
- `PageImage`: Pydantic model for an optional page image reference and description.
- `PageElement`: Pydantic model for one page element, including name, role, reference locators, and supported operations.
- `ReferenceLocator`: Pydantic model for a non-authoritative locator candidate observed for a page element, including confidence and notes.
- `ElementOperation`: Pydantic model for one supported operation on a page element and its result.
- `OperationResult`: Pydantic model for the operation result, optionally linking to a destination `page_id` when the operation is a graph transition.
- `GoalPrePlan`: Pydantic model returned by goal pre-planning. It contains the input goal, ordered key actions, relevant page ids, summary, and warnings.
- `GoalKeyAction`: Pydantic model for one ordered key action generated from a goal and page knowledge.
- `ToolDefinition`: Pydantic model describing a discovered local CLI, file, artifact, wait, secret, progress, visual assertion, shell, or harness-facing capability for diagnostics and CLI display.
- `ToolCall`: Pydantic model describing a tool invocation request.
- `ToolResult`: Pydantic model describing a normalized tool invocation response.
- Execution-core contract models: Pydantic models for StepRunner, HarnessInterface inputs/outputs, runner events, and EvidenceBundle manifests. These include `ExecutableStep`, `SourceRef`, `RetryPolicy`, `EvidencePolicy`, `StepCallInfo`, `StepPhaseReport`, `RunnerStepResult`, `RunnerEvent`, `HarnessContext`, `HarnessActionResult`, `HarnessArtifactRef`, `EvidenceBundle`, and `EvidenceManifest`.
- `HarnessFunctionSchema`: Pydantic model describing one concrete platform driver method that can be exposed as an OpenAI-compatible function schema. It contains the driver method name, description, strict parameter JSON schema, platform, Python driver method name, optional FSQ action provenance, and backend metadata. It is serializable only; it must not hold OpenAI Agents SDK runtime objects.
- `AndroidActionDefinition`: frozen dataclass for one Android FSQ action contract. It contains the FSQ action name, Python driver method name, shared Pydantic parameter model, and deterministic `ExecutableStep.kind`.
- `ANDROID_ACTION_DEFINITIONS`: ordered tuple of phase-1 Android action definitions.
- `ANDROID_ACTION_DEFINITIONS_BY_NAME`: lookup map from FSQ action name to `AndroidActionDefinition`. FSQ parsing, Android harness dispatch, and Android driver tool decoration must use this registry instead of maintaining separate hand-written action maps.
- `AndroidLocator`: Pydantic model for Android target locators with optional `resourceId`, `accessibilityId`, `text`, `className`, and `xpath` fields.
- `AndroidPoint`: Pydantic model for integer Android screen coordinates used by point-based swipes.
- `AndroidLaunchAppParams`: Pydantic model for `launch_app` driver parameters, including optional `app_id`.
- `AndroidKillAppParams`: Pydantic model for `kill_app` driver parameters, including optional `app_id`.
- `AndroidTapOnParams`: Pydantic model for `tap_on` parameters. It requires either a `target` string or a non-empty `locator`.
- `AndroidLongPressOnParams`: Pydantic model for `long_press_on` parameters. It uses the same target contract as `AndroidTapOnParams`.
- `AndroidInputTextParams`: Pydantic model for `input_text` parameters. It requires `text` plus either a `target` or non-empty `locator`.
- `AndroidPressKeyParams`: Pydantic model for `press_key` parameters with one normalized required key string.
- `AndroidSwipeParams`: Pydantic model for `swipe` parameters. It accepts either a direction string or both `start` and `end` points, with optional duration in milliseconds.
- `AndroidPerformActionsParams`: Pydantic model for `perform_actions` parameters that wraps a W3C actions array as `actions`.
- `AndroidAssertVisibleParams`: Pydantic model for `assert_visible` parameters. It uses the Android target contract plus optional assertion metadata.
- `AndroidAssertNotVisibleParams`: Pydantic model for `assert_not_visible` parameters. It uses the Android target contract plus optional assertion metadata.
- `AndroidTextAssertion`: Pydantic model for text assertion predicates, supporting `contains` and `equals`.
- `AndroidElementState`: Pydantic model for element locators plus expected boolean Android state fields `enabled`, `checked`, `selected`, `clickable`, and `focused`.
- `AndroidAssertStateParams`: Pydantic model for FSQ `assert` driver parameters. It supports `element` existence/state assertions and optional `text` assertions.
- `AndroidAssertWithAIParams`: Pydantic model for authored visual assertion parameters with a required prompt and optional assertion metadata. The concrete uiautomator2 backend must not expose this as a driver function schema unless it owns AI evaluation, but the harness may use it to validate authored strict-core steps.
- `OpenAIAgentsSettings`: Pydantic model for OpenAI Agents SDK provider configuration, including provider selection (`azure_openai` or `github_copilot`), Azure OpenAI base URL, API key environment variable, model deployment/name, tracing policy, turn limits, file-based prompt template customization, context trimming policy, and local tool output artifact policy. GitHub Copilot OAuth token storage is runtime-owned under the configured workspace and is not exposed as a YAML token setting. The agent runtime uses the Responses API for configured model providers.
- `PrePlanSettings`: Pydantic model for standalone goal pre-planning configuration, including the optional page-knowledge graph directory used instead of the normal task knowledge root.
- `VerificationSettings`: Pydantic model for the final verification policy. The default mode is `normal`.
- `OpenAIAgentPromptConfig`: Pydantic model containing optional Jinja template file paths, an optional custom operator instructions file path, short inline custom operator instructions, and scalar prompt variables.
- `ContextTrimmingSettings`: Pydantic model controlling SDK model-input trimming for older large tool outputs, including recent turn retention, maximum inline tool output size, preview size, and optional trimmable tool names.
- `LocalToolOutputSettings`: Pydantic model controlling how local SDK function tools write full outputs to per-run artifacts and decide whether model-facing responses contain full output or artifact references.
- `RuntimeSecretSettings`: Pydantic model listing environment variable names that local SDK tools may reveal to the model during a run. Values are loaded through normal environment or `.env` loading but are never stored in YAML case files.
- `HarnessSettings`: Pydantic model selecting the platform harness configuration used by goal-driven task execution.
- `AndroidHarnessSettings`: Pydantic model for the built-in Android harness runtime construction. It selects the Android backend, stores optional `app_id` and device `serial`, and controls whether authored AI assertions may use the configured AI assertion evaluator.
- `CLIToolConfig`: Pydantic model for configured CLI tools.
- `SkillConfig`: Pydantic model for one configured automation skill source.
- `SkillBundle`: Pydantic model containing loaded skill instructions, optional files, descriptions, and warnings.
- `AgentSettings`: Pydantic model for model name, step limits, timeouts, and retry defaults.
- `WorkspaceSettings`: Pydantic model for the managed fsq-agent workspace root, marker file name, and auto-initialization behavior.
- `CaseSettings`: Pydantic model for the read-only FSQ case directory.
- `ShellSettings`: Pydantic model for optional SDK `ShellTool` execution, including disabled-by-default local shell execution, `allowlist` mode, explicit high-trust `allow_all` mode, timeout, and working directory.
- `OutputSettings`: Pydantic model for the managed output root and per-run report directory. All logs, reports, tool artifacts, and generated files must live under the output root.
- `FsqAgentError`: Base exception for all project errors.
- `ConfigurationError`: Raised when configuration is missing or invalid.
- `PlanningError`: Raised when a task cannot be converted into an executable plan.
- `ToolExecutionError`: Raised when a tool call fails after retries or returns invalid output.
- `VerificationError`: Raised when verification cannot complete.
- `ReportGenerationError`: Raised when report generation fails.

## Internal Structure

- `__init__.py`: Public exports only.
- `_task.py`: Task, plan, step, result, and verification models.
- `_agent_io.py`: Structured agent task input, final output, plan item, schema version, and normalized tool-call record models.
- `_events.py`: Live run event model and event sink type alias.
- `_fsq.py`: FSQ AI Test DSL case metadata and case models.
- `_tools.py`: Tool metadata, tool call, tool result, and CLI config models.
- `_core.py`: Shared execution-core contract models for executable steps, runner phases/events, harness context/results, artifact references, evidence manifests, serializable harness function schemas, and Android driver parameter models used across `fsq` and `core`.
- `_settings.py`: Settings value models.
- `_skills.py`: Skill configuration and loaded skill bundle models.
- `_report.py`: Report artifact and evidence models.
- `_knowledge.py`: Knowledge bundle model.
- `_page_knowledge.py`: Public page-knowledge graph schema models and goal pre-plan output models.
- `_exceptions.py`: Shared exception hierarchy.
- `SPEC.md`: Module design.

## Error Handling

All custom exceptions inherit from `FsqAgentError`. Exceptions carry concise human-readable messages and optional structured context fields where useful. Other modules must import exception classes from this module rather than defining their own.

## Design Decisions

- Centralizing types prevents circular imports and inconsistent result schemas.
- New execution-core contracts must be added to this module rather than to `fsq_agent.core`, because cross-module data structures live only in `models`.
- Shared platform action parameter contracts must live in this module when they are consumed by more than one project module. Android strict-core parameter models and the Android action registry are shared by `fsq` for YAML normalization/step kind classification and by `core` for harness dispatch and action-space schema generation.
- `ANDROID_ACTION_DEFINITIONS_BY_NAME` is the single source of truth for phase-1 Android FSQ action name, driver method name, parameter model, and deterministic step kind. Modules must not maintain parallel handwritten maps for those fields.
- `HarnessFunctionSchema` is deliberately serializable. It is the single platform action function-call schema source and does not import or wrap OpenAI Agents SDK tool objects.
- Android driver parameter models forbid unexpected fields and provide canonical `model_dump(mode="json", exclude_none=True)` output. Runtime-only step metadata such as evidence policy, timeout fields, source references, retry policy, and step identifiers stays on `ExecutableStep` rather than inside driver parameter models.
- Pydantic is used at boundaries where external inputs, config files, agent output, and tool output enter the system.
- The agent final output contract is model-owned. The runtime always uses the current `AgentFinalOutput` schema through OpenAI Agents SDK structured output. The schema version is emitted in the final output for traceability, but schema selection is not a user-facing configuration.
- Task verification data is split from execution planning data as a breaking change. `key_actions` preserves every required ordered FSQ action for the execution agent, while `verification_criteria` records structured final-verification requirements. `acceptance_criteria` is no longer the primary contract for FSQ verification.
- Goal-only tasks may start with no `key_actions` and only goal-level verification criteria. If the agent orchestrator later derives key actions from `GoalPrePlan`, those generated actions are execution planning data only; they do not change the task's blocking final-verification criteria unless a caller explicitly supplies such criteria.
- Final verification strictness is model-owned through `VerificationSettings.mode`. `strict` requires every required `goal`, `assertion`, and `operation` criterion. `normal` requires required `goal` and `assertion` criteria while treating operation-only criteria as non-blocking execution evidence. `goal` requires only required `goal` criteria. A proven unmet goal criterion prevents success in every mode.
- Agent output schema evolution follows one of two policies: compatible evolution may only add fields without removing or changing existing field meaning; breaking evolution replaces the current schema and does not preserve a runtime switch for old formats.
- Tool-call reporting uses `ToolCallRecord` for real harness, local, and shell tool invocations. Runtime/provenance records such as pre-plan reconstruction and SDK runner summaries are not represented as real tool calls.
- Result models store evidence paths rather than binary evidence to keep logs and reports lightweight.
- Live run events are serializable and intentionally store user-visible summaries rather than hidden model chain-of-thought. Tool inputs and outputs may be redacted or preview-truncated by emitters before display or persistence.
- Context and local tool output settings are GPT-5.4 tuned by default: recent small or moderate tool outputs remain inline for fewer extra tool turns, while older or very large outputs are written to artifacts and represented by bounded previews.
- Runtime prompt text is template-owned through `OpenAIAgentPromptConfig`. The agent runtime assembles prompt models for knowledge, skills, task input, file-backed and inline custom instructions, and variables, then renders Jinja template files. Static behavioral text, headings, loops, and formatting should live in template files instead of hidden code paths or ad hoc string concatenation. Long operator instructions should live in a configured custom instructions file rather than inline YAML.
- Runtime secrets are model-owned as an allowlist of environment variable names. This keeps credential values out of cases and config YAML while allowing the tools module to expose only explicitly approved values to the SDK runner. Secret values must be redacted from user-visible events, artifact output, and final reports.
- Harness and driver selection is model-owned through `HarnessSettings` and platform-specific nested settings. Concrete platform behavior is implemented by the entry/runtime layer and the `core` harness/driver modules so configuration parsing does not own execution logic.
- fsq-agent does not expose MCP as a runtime capability path. Screenshots, UI trees, page sources, and other platform observations are represented by harness or local utility tool artifact references rather than by MCP tool output.
- Page knowledge is represented as a compact graph-like Markdown/JSON format owned by shared models so external generators can produce compatible files. `index.md` is a concise JSON index for page lookup; each `pages/*.md` file contains one JSON page node. Page identifiers are semantic descriptions without locators. Element locators are explicitly reference locators, not authoritative runtime truth.
- Goal pre-planning is represented separately from execution results. It produces ordered key actions from a natural-language goal and loaded page knowledge, but it does not execute UI actions or verify runtime state.
- OpenAI Agents SDK runtime objects are not stored directly in shared models. Models hold serializable configuration and harness function schemas that `agent` and `tools` adapt into SDK `Agent` and `FunctionTool` objects. `OpenAIAgentsSettings.provider` is the serialized switch for choosing Azure OpenAI or GitHub Copilot provider construction at runtime.
- Skills are descriptive instruction bundles. CLI/shell execution is controlled separately by configured CLI tools or `ShellSettings`.
- FSQ `.codex.yaml` cases are converted into `Task` descriptions for the agent loop. The parsed FSQ models preserve source metadata and command flow before rendering.
- Platform action parameter schemas come from `HarnessFunctionSchema` records returned by the active harness. There is no MCP schema validation fallback or MCP-derived tool schema source.
