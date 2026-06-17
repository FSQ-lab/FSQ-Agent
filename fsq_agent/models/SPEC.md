# Module: models

## Purpose

Own all shared data structures, strict replay reference models, configuration value models, result objects, CommonTool metadata, AI assertion request/result metadata, skill metadata, report metadata, and exception classes used across fsq-agent. This module is the only place where cross-module types and custom exceptions are defined.

## Dependencies

No project module dependencies. May depend on external libraries such as `pydantic` and standard library typing modules.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `Task`: Pydantic model describing a dynamic LLM goal/reference task, optional metadata, optional explicit planning reference kind/text, optional execution key actions, one final `verification_goal`, retry limits, timeout, and knowledge references. Only `description` is required. `planning_reference_kind` may identify first-party planning inputs such as `goal` or `raw_case`; `planning_reference_text` stores the authoritative text the pre-planner should use before falling back to legacy goal/description behavior. Execution key actions are planning context only; final verification checks `verification_goal` against execution evidence.
- `AGENT_FINAL_OUTPUT_SCHEMA_VERSION`: Constant containing the current supported final-output schema version. The runtime supports only the current schema; future compatible schema evolution may add fields, while breaking changes replace the current schema rather than exposing a user-selectable schema configuration.
- `AgentTaskInput`: Pydantic model describing the structured task envelope rendered into the model input. It includes a schema version, the task, complete key actions for execution planning, the single `verification_goal`, optional runtime policy text, and the final output contract name expected for the run.
- `AgentPlanItem`: Pydantic model for one planned or adjusted agent step in final output.
- `AgentFinalOutput`: Pydantic model for the OpenAI Agents SDK structured final output contract. It contains schema version, task status, summary, pre-plan, plan updates, goal-satisfaction claims, evidence, and errors.
- `ToolCallRecord`: Pydantic model for a normalized real tool invocation reconstructed from run events, including true tool name, origin (`harness`, `common`, `runtime`, or `unknown`), arguments, output preview, artifact reference, status, timing, and error fields.
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
- `GoalPrePlan`: Pydantic model used by internal dynamic goal planning. It contains the input goal/reference text, ordered key actions, one `verification_goal`, relevant page ids, summary, and warnings.
- `GoalKeyAction`: Pydantic model for one ordered key action generated from a goal/reference task and page knowledge.
- `CommonToolDefinition`: Pydantic model describing one SDK-neutral common utility capability, including name, description, strict JSON parameter schema, and metadata.
- `CommonToolCall`: Pydantic model describing one SDK-neutral common utility invocation request.
- `CommonToolResult`: Pydantic model describing a normalized common utility invocation response, including status, output, artifact reference, redaction metadata, duration, and error fields.
- `ToolDefinition`: Backward-compatible diagnostic alias for serializable tool/capability metadata during the migration to CommonTool. New code should prefer `CommonToolDefinition` for common utilities and `HarnessFunctionSchema` for platform actions.
- `ToolCall`: Backward-compatible diagnostic alias for serializable tool invocation requests during the migration to CommonTool. New code should prefer `CommonToolCall` for common utilities.
- `ToolResult`: Backward-compatible diagnostic alias for normalized tool invocation responses during the migration to CommonTool. New code should prefer `CommonToolResult` for common utilities.
- Execution-core contract models: Pydantic models for StepRunner, HarnessInterface inputs/outputs, runner events, and EvidenceBundle manifests. These include `ExecutableStep`, `SourceRef`, `RetryPolicy`, `EvidencePolicy`, `StepCallInfo`, `StepPhaseReport`, `RunnerStepResult`, `RunnerEvent`, `HarnessContext`, `HarnessActionResult`, `HarnessArtifactRef`, `EvidenceBundle`, and `EvidenceManifest`.
- `HarnessFunctionSchema`: Pydantic model describing one concrete platform harness or driver action that can be exposed as an OpenAI-compatible function schema. It contains the tool name, description, strict parameter JSON schema, platform, Python handler/driver method name, optional FSQ action provenance, and backend metadata. It is serializable only; it must not hold OpenAI Agents SDK runtime objects.
- `AndroidActionDefinition`: frozen dataclass for one Android FSQ action contract. It contains the FSQ action name, Python handler/driver method name, shared Pydantic parameter model, deterministic `ExecutableStep.kind`, and enough metadata for `AndroidHarness` to distinguish driver-owned actions from harness-owned actions such as `assertWithAI`.
- `ANDROID_ACTION_DEFINITIONS`: ordered tuple of phase-1 Android action definitions.
- `ANDROID_ACTION_DEFINITIONS_BY_NAME`: lookup map from FSQ action name to `AndroidActionDefinition`. FSQ parsing, Android harness dispatch, and Android driver tool decoration must use this registry instead of maintaining separate hand-written action maps.
- `AndroidLocator`: Pydantic model for Android target locators with optional `resourceId`, `accessibilityId`, `text`, `className`, and `xpath` fields.
- `RuntimeSecretRef`: Pydantic model for one strict replay runtime-secret reference. Its serialized YAML/JSON shape is `{"runtimeSecret": "ENV_NAME"}`. It stores only the environment variable name and never a secret value.
- `WaitMsParams`: Pydantic model for FSQ strict replay `waitMs` commands. It contains a bounded `duration_ms` value and optional reason text, and represents a pure elapsed-time wait that must not touch platform state.
- `AndroidPoint`: Pydantic model for integer Android screen coordinates used by point-based swipes.
- `AndroidLaunchAppParams`: Pydantic model for `launch_app` driver parameters, including optional `app_id`.
- `AndroidKillAppParams`: Pydantic model for `kill_app` driver parameters, including optional `app_id`.
- `AndroidTapOnParams`: Pydantic model for `tap_on` parameters. It requires either a `target` string or a non-empty `locator`.
- `AndroidLongPressOnParams`: Pydantic model for `long_press_on` parameters. It uses the same target contract as `AndroidTapOnParams`.
- `AndroidInputTextParams`: Pydantic model for resolved `input_text` parameters. It requires string `text` plus either a `target` or non-empty `locator`. Strict replay refs such as `RuntimeSecretRef` may appear in parsed FSQ command payloads before strict entry resolution, but they are not valid Android driver parameters after resolution.
- `AndroidPressKeyParams`: Pydantic model for `press_key` parameters with one normalized required key string.
- `AndroidSwipeParams`: Pydantic model for `swipe` parameters. It accepts either a direction string or both `start` and `end` points, with optional duration in milliseconds.
- `AndroidUiTreeParams`: Pydantic model for the read-only `ui_tree` driver tool parameters. It accepts no fields and exists so dynamic agents can request the current Android UI hierarchy through the normal harness action schema path.
- `AndroidPerformActionsParams`: Pydantic model for `perform_actions` parameters that wraps a W3C actions array as `actions`.
- `AndroidAssertVisibleParams`: Pydantic model for `assert_visible` parameters. It uses the Android target contract plus optional assertion metadata.
- `AndroidAssertNotVisibleParams`: Pydantic model for `assert_not_visible` parameters. It uses the Android target contract plus optional assertion metadata.
- `AndroidTextAssertion`: Pydantic model for text assertion predicates, supporting `contains` and `equals`.
- `AndroidElementState`: Pydantic model for element locators plus expected boolean Android state fields `enabled`, `checked`, `selected`, `clickable`, and `focused`.
- `AndroidAssertStateParams`: Pydantic model for FSQ `assert` driver parameters. It supports `element` existence/state assertions and optional `text` assertions.
- `AndroidAssertWithAIParams`: Pydantic model for authored Android visual assertion parameters with a required prompt and optional assertion metadata. This parameter model is consumed by `AndroidHarness`; concrete Android drivers must not call providers or expose this as a driver-owned function schema.
- `AIAssertionRequest`: Pydantic model describing one provider-backed platform visual assertion request. It includes platform, prompt, screenshot artifact reference or screenshot path, optional UI/context metadata, run/step metadata, and provider/model metadata fields safe for reports.
- `AIAssertionResult`: Pydantic model describing one provider-backed platform visual assertion verdict. It includes status/pass boolean, explanation, confidence when available, provider/model metadata, token/latency diagnostics when safe, and evidence artifact references. It must not contain raw secret values or hidden model reasoning.
- `OpenAIAgentsSettings`: Pydantic model for OpenAI Agents SDK provider configuration, including provider selection (`github_copilot` by default, or explicit `azure_openai`), tracing policy, turn limits, file-based prompt template customization, internal context trimming policy, internal CommonTool output artifact policy, and resolved provider runtime values. GitHub Copilot uses fixed model `gpt-5.5`; Azure OpenAI endpoint, deployment/model, and API key are sourced from fixed environment variable names by configuration loading rather than from YAML fields. GitHub Copilot OAuth token storage is runtime-owned under the configured workspace and is not exposed as a YAML token setting. The agent runtime uses the Responses API for configured model providers.
- `OpenAIAgentPromptConfig`: Pydantic model containing optional Jinja template file paths, an optional custom operator instructions file path, short inline custom operator instructions, and scalar prompt variables.
- `ContextTrimmingSettings`: Pydantic model controlling SDK model-input trimming for older large tool outputs, including recent turn retention, maximum inline tool output size, preview size, and optional trimmable tool names. These values are internal runtime defaults and are not part of the default YAML surface.
- `LocalToolOutputSettings`: Pydantic model controlling how local SDK function tools write full outputs to per-run artifacts and decide whether model-facing responses contain full output or artifact references. These values are internal runtime defaults and one-option policy fields should not be exposed as YAML knobs.
- `RuntimeSecretSettings`: Pydantic model listing environment variable names that local SDK tools may reveal to the model during a run. Values are loaded through normal environment or `.env` loading but are never stored in YAML case files.
- `HarnessSettings`: Pydantic model selecting the platform harness configuration used by goal-driven task execution. It contains platform-specific harness settings and `strict_core` pacing settings owned by harness execution.
- `AndroidHarnessSettings`: Pydantic model for the built-in Android harness runtime construction. YAML selects the Android backend; configuration loading fills optional `app_id` and device `serial` from `FSQ_ANDROID_APP_ID` and `FSQ_ANDROID_SERIAL`. Strict-core execution does not enable AI assertion evaluators through this settings model.
- `StrictCoreHarnessSettings`: Pydantic model for deterministic strict-core harness pacing. `step_interval_seconds` defaults to `1.0`, must be non-negative, and is passed to `StepSequenceRunner` by entry-layer strict execution. It is timing-only and must not be serialized into FSQ commands or evidence as a synthetic step.
- `AgentContextSettings`: Pydantic model grouping knowledge-root resources used to build agent context.
- `AgentKnowledgeSettings`: Pydantic model containing the configured private knowledge `root_dir`, nested skill resource configuration, and optional pre-plan page-knowledge configuration.
- `KnowledgeSkillSettings`: Pydantic model containing the skill directory under the knowledge root and the configured `SkillConfig` items loaded from that directory.
- `PrePlanKnowledgeSettings`: Pydantic model containing the optional page-knowledge graph directory under the knowledge root. When omitted, internal dynamic pre-plan uses the normal knowledge root.
- `SkillConfig`: Pydantic model for one configured automation skill source.
- `SkillBundle`: Pydantic model containing loaded skill instructions, optional files, descriptions, and warnings.
- `AgentSettings`: Pydantic model for agent-level execution defaults such as step timeout. Model selection belongs to `OpenAIAgentsSettings`, and inactive loop/retry knobs are not part of the public YAML surface.
- `WorkspaceSettings`: Pydantic model for the managed fsq-agent workspace root. Marker file name and auto-initialization behavior are internal workspace policy rather than YAML settings.
- `CaseSettings`: Pydantic model for the read-only FSQ case directory.
- `OutputSettings`: Pydantic model for the managed output root. The per-run report/artifact layout under the output root is internal policy. All logs, reports, tool artifacts, and generated files must live under the output root.
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
- `_tools.py`: CommonTool metadata/call/result models plus temporary backward-compatible diagnostic tool aliases.
- `_ai_assertion.py`: Provider-backed platform AI assertion request/result models.
- `_core.py`: Shared execution-core contract models for executable steps, strict replay refs, pure wait params, runner phases/events, harness context/results, artifact references, evidence manifests, serializable harness function schemas, and Android driver parameter models used across `fsq`, `cli`, and `core`.
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
- Shared platform action parameter contracts and strict replay reference contracts must live in this module when they are consumed by more than one project module. Android strict-core parameter models and the Android action registry are shared by `fsq` for YAML normalization/step kind classification and by `core` for harness dispatch and action-space schema generation. Strict replay references are shared by `fsq` parsing and `cli` strict replay resolution.
- `ANDROID_ACTION_DEFINITIONS_BY_NAME` is the single source of truth for phase-1 Android FSQ action name, handler/driver method name, parameter model, deterministic step kind, and harness-vs-driver ownership metadata. Modules must not maintain parallel handwritten maps for those fields.
- `uiTree` is a driver-owned, read-only observation action in the Android action registry. It is exposed to dynamic agents as `ui_tree`, returns the current backend UI hierarchy, and is not an authored FSQ command currently used by strict replay cases.
- `HarnessFunctionSchema` is deliberately serializable. It is the single platform action function-call schema source and does not import or wrap OpenAI Agents SDK tool objects. Harness-owned platform actions such as Android `assertWithAI` use the same schema path as driver-backed platform actions.
- Android driver parameter models forbid unexpected fields and provide canonical `model_dump(mode="json", exclude_none=True)` output. Runtime-only step metadata such as evidence policy, timeout fields, source references, retry policy, replay-source metadata, and step identifiers stays on `ExecutableStep` rather than inside driver parameter models.
- `RuntimeSecretRef` is a pre-resolution FSQ replay reference, not a driver parameter value. Strict entry-layer code must resolve it to a string in memory and then validate the resolved payload against the appropriate Android driver parameter model before `core` invokes a harness.
- `WaitMsParams` is a core-owned strict replay command model, not an Android driver parameter model and not a CommonTool model. It lets recorded strict cases replay pure waits without routing through Android gesture or driver APIs.
- Pydantic is used at boundaries where external inputs, config files, agent output, and tool output enter the system.
- The agent final output contract is model-owned. The runtime always uses the current `AgentFinalOutput` schema through OpenAI Agents SDK structured output. The schema version is emitted in the final output for traceability, but schema selection is not a user-facing configuration.
- Task verification data is split from execution planning data. `key_actions` preserves caller-supplied or internally generated execution guidance, while `verification_goal` records the single final outcome the evidence-based verifier must check. Dynamic CLI inputs do not use typed assertion/operation verifier contracts or configurable verification modes.
- Task planning references are distinct from task descriptions and verification requirements. `planning_reference_kind` and `planning_reference_text` are optional compatibility fields for pre-plan input selection; first-party dynamic CLI tasks should populate them so pre-planning does not infer execution flow from final verification text. Raw case planning references preserve authored file content as text and must not imply parsed strict execution.
- Goal/reference tasks may start with no `key_actions` and no final verification goal. The agent orchestrator must run pre-plan before external UI actions, then copy the returned `GoalPrePlan.key_actions` into `Task.key_actions` and the returned `GoalPrePlan.verification_goal` into `Task.verification_goal`. Generated key actions are execution planning data only and must not become additional final-verifier requirements.
- Dynamic final verification is goal-only. The verifier checks one `verification_goal` string and returns success only when execution evidence supports that goal, failed when evidence proves the goal unmet, and inconclusive when evidence is insufficient or ambiguous.
- Agent output schema evolution follows one of two policies: compatible evolution may only add fields without removing or changing existing field meaning; breaking evolution replaces the current schema and does not preserve a runtime switch for old formats.
- Tool-call reporting uses `ToolCallRecord` for real harness and common tool invocations. Runtime/provenance records such as progress events, pre-plan reconstruction, SDK runner summaries, and provider session setup are not represented as real tool calls.
- Result models store evidence paths rather than binary evidence to keep logs and reports lightweight.
- Live run events are serializable and intentionally store user-visible summaries rather than hidden model chain-of-thought. Tool inputs and outputs may be redacted or preview-truncated by emitters before display or persistence.
- Context and CommonTool output settings are internal runtime defaults: recent small or moderate tool outputs remain inline for fewer extra tool turns, while older or very large outputs are written to artifacts and represented by bounded previews.
- Runtime prompt text is template-owned through `OpenAIAgentPromptConfig`. The agent runtime assembles prompt models for knowledge, skills, task input, file-backed and inline custom instructions, and variables, then renders Jinja template files. Static behavioral text, headings, loops, and formatting should live in template files instead of hidden code paths or ad hoc string concatenation. Long operator instructions should live in a configured custom instructions file rather than inline YAML.
- Runtime secrets are model-owned as an allowlist of environment variable names. This keeps credential values out of cases and config YAML while allowing the tools module to expose only explicitly approved values to the SDK runner and allowing recorded strict cases to reference approved names through `RuntimeSecretRef`. Secret values must be redacted from user-visible events, artifact output, model-facing previews, strict evidence, recording manifests, and final reports.
- CommonTool request/result models are serializable and SDK-neutral. The tools module adapts them to OpenAI Agents SDK `FunctionTool` objects, but shared models must not import SDK types.
- AI assertion request/result models are serializable execution evidence. They describe explicit authored platform assertions and provider-backed verdicts; they do not represent locator fallback, testcase mutation, recovery, or hidden model reasoning.
- Harness and driver selection is model-owned through `HarnessSettings` and platform-specific nested settings. Strict-core step interval is also harness-owned through `HarnessSettings.strict_core` because it controls deterministic harness execution pacing, not provider behavior, dynamic recording logic, or FSQ command semantics. Concrete platform behavior is implemented by the entry/runtime layer and the `core` harness/driver modules so configuration parsing does not own execution logic.
- fsq-agent does not expose MCP as a runtime capability path. Screenshots, UI trees, page sources, and other platform observations are represented by harness or CommonTool artifact references rather than by MCP tool output.
- Page knowledge is represented as a compact graph-like Markdown/JSON format owned by shared models so external generators can produce compatible files. `index.md` is a concise JSON index for page lookup; each `pages/*.md` file contains one JSON page node. Page identifiers are semantic descriptions without locators. Element locators are explicitly reference locators, not authoritative runtime truth.
- Internal dynamic goal planning is represented separately from execution results. It produces ordered key actions from a goal/reference task and loaded page knowledge, but it does not execute UI actions or verify runtime state.
- OpenAI Agents SDK runtime objects are not stored directly in shared models. Models hold serializable configuration, common tool definitions, AI assertion request/results, and harness function schemas that `agent`, `tools`, and `providers` adapt into runtime objects. `OpenAIAgentsSettings.provider` is the serialized switch for choosing GitHub Copilot or Azure OpenAI provider construction at runtime. Provider endpoint/key/model values that are local to a user or deployment are resolved by `config` from fixed environment variable names instead of stored as YAML fields.
- Skills are descriptive instruction bundles stored under the configured agent knowledge root. `agent_context.knowledge.skills.dir` locates the skill files relative to `agent_context.knowledge.root_dir` by default, and `agent_context.knowledge.skills.items` lists the configured bundles. Skills do not grant CLI or shell execution.
- Agent context configuration groups related context resources under `agent_context.knowledge`: the normal private knowledge root, the skills subdirectory and items under that root, and optional pre-plan page knowledge under the same root. Top-level `skills`, top-level `knowledge_dir`, and top-level `pre_plan` are not part of the public YAML surface.
- Parsed FSQ `.codex.yaml` models are used for strict-core execution. The public CLI's default LLM `--case-yaml` and `--case-dir` paths read YAML files as raw text and build goal/reference `Task` values without parsed FSQ models.
- Platform action parameter schemas come from `HarnessFunctionSchema` records returned by the active harness. There is no MCP schema validation fallback or MCP-derived tool schema source.
