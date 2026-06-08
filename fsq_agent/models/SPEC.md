# Module: models

## Purpose

Own all shared data structures, configuration value models, result objects, tool metadata, skill metadata, report metadata, and exception classes used across fsq-agent. This module is the only place where cross-module types and custom exceptions are defined.

## Dependencies

No project module dependencies. May depend on external libraries such as `pydantic` and standard library typing modules.

## Public Interface

Current `__init__.py` exports via `__all__`:

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
- `MCPToolValidationSettings`: Pydantic model controlling startup-time MCP tool compatibility checks, including enabled state, invalid tool policy, strict schema conversion, unsupported schema keyword checks, and all-tools-filtered behavior.
- `MCPToolValidationIssue`: Pydantic model describing one MCP tool that was ignored or failed validation, including server name, tool name, reason, policy, and schema path.
- `ToolDefinition`: Pydantic model describing a discovered MCP, CLI, or file operation capability.
- `ToolCall`: Pydantic model describing a tool invocation request.
- `ToolResult`: Pydantic model describing a normalized tool invocation response.
- Planned execution-core contract models: Pydantic models for StepRunner, HarnessInterface inputs/outputs, runner events, and EvidenceBundle manifests. These include `ExecutableStep`, `SourceRef`, `RetryPolicy`, `EvidencePolicy`, `StepCallInfo`, `StepPhaseReport`, core `StepResult` equivalent naming to be finalized before implementation, `RunnerEvent`, `HarnessContext`, `HarnessActionResult`, `HarnessArtifactRef`, `EvidenceBundle`, and `EvidenceManifest`. Exact public names must be confirmed before implementation to avoid ambiguity with the existing `StepResult` model.
- `OpenAIAgentsSettings`: Pydantic model for OpenAI Agents SDK provider configuration, including provider selection (`azure_openai` or `github_copilot`), Azure OpenAI base URL, API key environment variable, model deployment/name, tracing policy, turn limits, file-based prompt template customization, context trimming policy, and local tool output artifact policy. GitHub Copilot OAuth token storage is runtime-owned under the configured workspace and is not exposed as a YAML token setting. The agent runtime uses the Responses API for configured model providers.
- `PrePlanSettings`: Pydantic model for standalone goal pre-planning configuration, including the optional page-knowledge graph directory used instead of the normal task knowledge root.
- `VerificationSettings`: Pydantic model for the final verification policy. The default mode is `normal`.
- `OpenAIAgentPromptConfig`: Pydantic model containing optional Jinja template file paths, an optional custom operator instructions file path, short inline custom operator instructions, and scalar prompt variables.
- `ContextTrimmingSettings`: Pydantic model controlling SDK model-input trimming for older large tool outputs, including recent turn retention, maximum inline tool output size, preview size, and optional trimmable tool names.
- `LocalToolOutputSettings`: Pydantic model controlling how local SDK function tools write full outputs to per-run artifacts and decide whether model-facing responses contain full output or artifact references.
- `RuntimeSecretSettings`: Pydantic model listing environment variable names that local SDK tools may reveal to the model during a run. Values are loaded through normal environment or `.env` loading but are never stored in YAML case files.
- `LifecycleControllerSettings`: Pydantic model selecting the named setup/teardown controller implementation and passing implementation-specific options.
- `MCPServerConfig`: Pydantic model for OpenAI Agents SDK MCP configuration. Supports `stdio`, `streamable_http`, `sse`, and `hosted` transports plus approval policy, headers, manual tool filters, and prompt loading policy.
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
- `_tools.py`: Tool metadata, tool call, tool result, MCP validation issue/settings, MCP config, and CLI config models.
- Planned `_core.py`: Shared execution-core contract models for executable steps, runner phases/events, harness context/results, artifact references, and evidence manifests. This file should be added only after `core` and `models` SPEC changes are reviewed and confirmed.
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
- Pydantic is used at boundaries where external inputs, config files, agent output, and tool output enter the system.
- The agent final output contract is model-owned. The runtime always uses the current `AgentFinalOutput` schema through OpenAI Agents SDK structured output. The schema version is emitted in the final output for traceability, but schema selection is not a user-facing configuration.
- Task verification data is split from execution planning data as a breaking change. `key_actions` preserves every required ordered FSQ action for the execution agent, while `verification_criteria` records structured final-verification requirements. `acceptance_criteria` is no longer the primary contract for FSQ verification.
- Goal-only tasks may start with no `key_actions` and only goal-level verification criteria. If the agent orchestrator later derives key actions from `GoalPrePlan`, those generated actions are execution planning data only; they do not change the task's blocking final-verification criteria unless a caller explicitly supplies such criteria.
- Final verification strictness is model-owned through `VerificationSettings.mode`. `strict` requires every required `goal`, `assertion`, and `operation` criterion. `normal` requires required `goal` and `assertion` criteria while treating operation-only criteria as non-blocking execution evidence. `goal` requires only required `goal` criteria. A proven unmet goal criterion prevents success in every mode.
- Agent output schema evolution follows one of two policies: compatible evolution may only add fields without removing or changing existing field meaning; breaking evolution replaces the current schema and does not preserve a runtime switch for old formats.
- Tool-call reporting uses `ToolCallRecord` for real local/MCP/hosted/shell tool invocations. Runtime/provenance records such as pre-plan reconstruction and SDK runner summaries are not represented as real tool calls.
- Result models store evidence paths rather than binary evidence to keep logs and reports lightweight.
- Live run events are serializable and intentionally store user-visible summaries rather than hidden model chain-of-thought. Tool inputs and outputs may be redacted or preview-truncated by emitters before display or persistence.
- Context and local tool output settings are GPT-5.4 tuned by default: recent small or moderate tool outputs remain inline for fewer extra tool turns, while older or very large outputs are written to artifacts and represented by bounded previews.
- Runtime prompt text is template-owned through `OpenAIAgentPromptConfig`. The agent runtime assembles prompt models for knowledge, skills, task input, file-backed and inline custom instructions, and variables, then renders Jinja template files. Static behavioral text, headings, loops, and formatting should live in template files instead of hidden code paths or ad hoc string concatenation. Long operator instructions should live in a configured custom instructions file rather than inline YAML.
- Runtime secrets are model-owned as an allowlist of environment variable names. This keeps credential values out of cases and config YAML while allowing the tools module to expose only explicitly approved values to the SDK runner. Secret values must be redacted from user-visible events, artifact output, and final reports.
- Setup and teardown lifecycle selection is model-owned through `LifecycleControllerSettings`. The setting stores a controller name and opaque options; concrete behavior is implemented by the tools module so platform/MCP-specific logic does not leak into config parsing.
- fsq-agent does not own native screenshot or UI tree capture settings. Those observations are used only when supplied by configured MCP servers or tools.
- Page knowledge is represented as a compact graph-like Markdown/JSON format owned by shared models so external generators can produce compatible files. `index.md` is a concise JSON index for page lookup; each `pages/*.md` file contains one JSON page node. Page identifiers are semantic descriptions without locators. Element locators are explicitly reference locators, not authoritative runtime truth.
- Goal pre-planning is represented separately from execution results. It produces ordered key actions from a natural-language goal and loaded page knowledge, but it does not execute UI actions or verify runtime state.
- OpenAI Agents SDK runtime objects are not stored directly in shared models. Models hold serializable configuration that `agent` and `tools` adapt into SDK `Agent`, `FunctionTool`, `MCPServer*`, and hosted tool objects. `OpenAIAgentsSettings.provider` is the serialized switch for choosing Azure OpenAI or GitHub Copilot provider construction at runtime.
- Skills are descriptive instruction bundles. CLI/shell execution is controlled separately by configured CLI tools or `ShellSettings`.
- FSQ `.codex.yaml` cases are converted into `Task` descriptions for the agent loop. The parsed FSQ models preserve source metadata and command flow before rendering.
- MCP tool validation settings are global runtime policy. Per-server `allowed_tools` and `blocked_tools` remain explicit operator controls and are combined with automatically detected invalid tools during MCP server startup.
