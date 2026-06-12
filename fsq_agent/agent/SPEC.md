# Module: agent

## Purpose

Coordinate dynamic goal/reference testing workflows using OpenAI Agents SDK: load runtime settings, construct or receive the configured harness, obtain the shared provider session from `providers`, build the OpenAI-compatible agent, attach CommonTool utility tools and harness-generated platform action tools, load relevant knowledge and skills, derive execution and verification context from a natural-language goal or raw reference content, execute and dynamically adjust through SDK-managed tool calls, persist recordable safe event metadata for post-run recording, derive verification status from structured final output according to configured verification mode, and trigger report generation.

## Dependencies

- `models`: Uses all task, plan, structured agent IO, result, tool, report, event, and exception models.
- `config`: Uses runtime settings.
- `providers`: Builds shared Azure OpenAI or GitHub Copilot provider sessions and provider-backed evaluator dependencies.
- `core`: Uses `HarnessInterface` implementations and shared harness behavior through public core exports supplied by entry/runtime construction.
- `tools`: Builds CommonTool OpenAI Agents SDK utility tools and exposes diagnostic capabilities.
- `observation`: Captures evidence after steps.
- `knowledge`: Loads private knowledge.
- `skills`: Loads configured automation skill instruction bundles.
- `report`: Generates reports and evidence bundles.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `FsqAgent`: Main orchestration class.
- `OpenAIAgentsRuntime`: Builds and runs an OpenAI Agents SDK `Agent` with a provider session supplied by `providers`, CommonTool utility tools, harness-generated platform action tools, skills, turn limits, and tracing policy.
- `Verifier`: Parses structured verifier-agent or runner final output and converts task status, satisfied criteria, unmet criteria, evidence, diagnostics, and configured verification mode into a `VerificationResult`.

Planned signatures:

- `FsqAgent.from_config(path: str | Path | None = None, workspace: str | Path | None = None) -> FsqAgent`
- `FsqAgent.from_settings(settings: Settings) -> FsqAgent`
- `FsqAgent.run(task: Task, event_sink: RunEventSink | None = None) -> TaskResult`
- `OpenAIAgentsRuntime.run_task(task: Task, knowledge: KnowledgeBundle, skills: list[SkillBundle], run_id: str, event_sink: RunEventSink | None = None) -> list[StepResult]`
- `Verifier.verify(task: Task, results: list[StepResult], events_path: Path | None = None, mode: VerificationMode = "normal") -> VerificationResult`

## Internal Structure

- `__init__.py`: Public exports only.
- `_core.py`: `FsqAgent` orchestration and lifecycle.
- `_events.py`: Run event emission, sequencing, persistence fan-out, and user-sink dispatch.
- `_openai_runtime.py`: OpenAI Agents SDK runtime assembly using provider sessions from `providers`, harness construction or injection, CommonTool and harness tool assembly, agent construction, `Runner.run_streamed` invocation, and SDK stream event mapping.
- `_harness_tools.py`: Harness `FunctionTool` adapter that converts `HarnessFunctionSchema` records into SDK tools, maps SDK tool arguments into `ExecutableStep` records, invokes `HarnessInterface`, and serializes `HarnessActionResult` records to bounded model-visible JSON with safe structured status/provenance fields suitable for reports and post-run recording.
- `_pre_plan.py`: Internal prompt instructions and helpers for dynamic goal planning from page knowledge when directly invoked by `FsqAgent.run`.
- `_prompt.py`: Prompt model construction and template rendering for agent instructions and task input.
- `_structured_output.py`: Shared coercion helpers for SDK final output values and compatibility parsing of legacy/raw final JSON strings.
- `_verification_task.py`: Builds an evidence bundle from task context, execution records, event logs, and persisted tool artifacts for a separate evidence-based verification agent task.
- `_verifier.py`: Acceptance criteria verification and failure diagnostics.
- `SPEC.md`: Module design.

## Error Handling

Configuration errors are raised before task execution when OpenAI Agents SDK is disabled, required provider credentials are absent, harness construction fails, CommonTool construction fails, or harness action-space conversion fails. SDK, harness, or CommonTool runtime exceptions are converted into failed `StepResult` values so report generation can still complete. Synchronous harness construction during main execution startup is bounded by `agent.step_timeout_seconds`; timeout or construction failure emits a run failure event and returns a failed runner `StepResult` instead of waiting silently. Recoverable tool failures should be surfaced through structured final JSON. Verification treats invalid final JSON as inconclusive instead of claiming task success.

Internal goal planning raises configuration errors when OpenAI Agents SDK configuration is unavailable and planning errors when the SDK does not return a valid `GoalPrePlan`. Planning used inside `FsqAgent.run` does not construct platform harnesses, call UI/external action tools, or generate separate reports. Read-only knowledge lookup tool failures are surfaced to the planner as warnings so it can continue when possible.

During `FsqAgent.run`, a task with no caller-supplied ordered key actions may be internally planned before external UI actions begin. The orchestrator uses the task's explicit planning reference text and kind when present, falling back to legacy goal/description selection only for compatibility, converts returned `GoalKeyAction` values into `Task.key_actions` as execution guidance only, emits planning events on the same run timeline, and then executes the normal task runtime. Generated key actions must not become additional blocking final-verification criteria. If planning returns no key actions, execution still proceeds with the original goal/reference task and a warning event; if planning raises an error, the task run fails before external actions are attempted.

## Design Decisions

- The orchestration module depends on all leaf modules, but leaf modules never depend on `agent`.
- OpenAI Agents SDK is the selected agent runtime and tool-use integration layer for this project.
- Azure OpenAI and GitHub Copilot provider construction is delegated to `providers`. `agent` asks for a configured provider session and uses that session to create the OpenAI Agents SDK provider object for `RunConfig`. Provider authentication, endpoint selection, token caching, Copilot plan detection, and direct Responses-style model invocation are not implemented in `agent`.
- Task execution requires the OpenAI Agents SDK package and provider authentication to be available through `providers`. There is no offline fallback execution path.
- The SDK runner owns tool dispatch and turn continuation. The project should not reimplement the Responses function-call loop.
- Platform action tools are generated from the active harness. `OpenAIAgentsRuntime` reads `HarnessInterface.action_space()`, converts each `HarnessFunctionSchema` into one SDK `FunctionTool`, and creates SDK agents with no external platform tool servers. Harness-owned `assert_with_ai` is a platform action tool when exposed by the harness, not a common utility tool.
- Main execution startup is observable before the first SDK planning turn. `OpenAIAgentsRuntime.run_task` emits runtime progress events for startup, harness setup, tool setup, and SDK agent readiness before the existing main `Planning started` event. Harness setup events include only safe metadata such as platform, backend, app id presence, serial presence, timeout seconds, and driver class when available.
- Harness construction remains a synchronous platform concern internally, but dynamic main execution wraps it in an async-compatible timeout boundary. The runtime calls the configured harness factory or built-in harness construction through a worker-thread helper and applies `agent.step_timeout_seconds` as the startup timeout. A timed-out worker result is ignored after the runtime has returned a failed runner step; no UI action should be invoked from that timed-out path.
- The harness tool adapter must preserve schema provenance, including platform, driver method, and optional `fsq_action_name`, in run events and tool result metadata.
- When the SDK calls a harness tool, the adapter parses JSON arguments, builds an `ExecutableStep`, calls `harness.get_context()`, invokes `harness.invoke_action(step, context)`, and returns compact JSON derived from `HarnessActionResult`.
- A harness action failure should normally be returned as a successful SDK tool transport result whose JSON has `status="failed"`, `failure_category`, `error_message`, output preview, and artifact refs. Unexpected adapter failures are converted into structured failed tool JSON or failed `StepResult` records depending on when they occur. Tool output events for harness calls should include safe structured payload fields for `tool_origin`, true tool name, platform, driver method, `fsq_action_name`, status, failure category, and artifact path when known so CLI recording does not need to parse truncated previews.
- Harness action-space discovery or SDK tool conversion failures are startup configuration errors. The runtime must not silently expose a partial harness action list.
- The agent may create an internal plan before external actions, derive task success criteria from the description, private knowledge, and skills when the caller did not provide criteria, execute through harness and CommonTool utility tools, and adapt the plan when tool feedback changes the best path.
- Standalone goal pre-planning is not a public CLI or module API. Any retained pre-planning implementation is internal to normal LLM execution.
- Internal planning receives a structured reference envelope containing `reference_type` and `reference_text`, loads the concise page index from `pre_plan.knowledge_dir` when configured or from `knowledge_dir` as a fallback, and returns ordered key actions plus relevant page ids. It is side-effect-free for the application under test: no UI automation, no lifecycle calls, no verification agent, and no separate report generation.
- For `reference_type="raw_case"`, the pre-planner must first derive the authored ordered flow from the raw case text and then use page knowledge as auxiliary grounding for page semantics, locator hints, transitions, and warnings. Raw case flow wins over incomplete or mismatched page knowledge; mismatches should be recorded as warnings rather than silently replacing authored steps. Lifecycle commands such as `launchApp` and `killApp` may be represented as setup/teardown intent instead of ordinary business key actions unless they are semantically central to the case.
- Generated key actions become the execution spine only; final verification remains governed by the original task's goal-level criteria and configured verification mode.
- Pre-planning is an iterative knowledge loop. The initial model input contains `index.md` only. The pre-plan agent can call read-only local knowledge tools to reload the index or load specific page files from `knowledge/pages/` by page id or relative path. Page-to-page transitions may cause additional page reads until the action chain is complete or no useful next page is available.
- If page knowledge is incomplete, the planner should still produce the best available contiguous key-action chain. It may skip at most one consecutive missing action by recording a warning. If it cannot produce a useful plan from the available graph, it must return a valid `GoalPrePlan` with an empty `key_actions` list.
- When a caller supplies ordered key actions, the runtime must use the complete list as the execution spine regardless of final verification mode: preserve their relative order, allow recovery/setup/dialog-handling steps between them, and collect live evidence for the resulting state before reporting success. The public CLI no longer supplies parsed FSQ command-derived key actions for normal LLM `--case-yaml` or `--case-dir` runs.
- Ordered key actions must preserve semantic fidelity. Recovery or fallback actions may restore UI state, but they do not satisfy the original ordered key action unless they perform the same accepted semantic action. Tool usage errors should be corrected for the same semantic action before switching to non-equivalent fallback routes.
- Run identifiers are generated by the orchestration layer as `<task-id>-YYYY-MM-DD_HH-MM-SS` using local time so directories under `output.runs_dir` are easy to read while remaining path-safe on Windows.
- Task runs emit live `RunEvent` values for planning summaries, harness/CommonTool SDK tool calls, runtime-internal progress, tool outputs, failures, and completion. Events are for user-visible progress, reports, and post-run recording metadata, and must not expose hidden model chain-of-thought. Runtime interruptions such as debugger cancellation or keyboard interrupt emit a final `run_failed` event before being re-raised.
- The runtime consumes OpenAI Agents SDK streaming semantic events through `Runner.run_streamed(...).stream_events()` and maps them into `RunEvent` values while preserving the final output path used by verification and reporting.
- The runtime configures the OpenAI Agents SDK `call_model_input_filter` with `ToolOutputTrimmer` plus a project filter that preserves the most recent configured number of function tool outputs by tool-call count. This keeps recent outputs at full fidelity while trimming older large tool outputs before each model call.
- The project filter persists SDK function-call outputs, including harness and CommonTool utility outputs when represented as function-call output items, into the current run's tool artifact directory before replacing historical oversized content with a bounded preview and artifact path.
- Visual assertion image handling is owned by the platform harness and provider-backed evaluator. The main runner does not use a local `submit_visual_assertion` tool or screenshot-to-next-turn attachment filter. When the model needs an authored Android `assertWithAI`, it calls the harness `assert_with_ai` platform action; the harness captures a screenshot, calls its injected evaluator, and returns a verdict as tool output evidence.
- Runtime instructions tell the agent that CommonTool outputs may include artifact references and that `search_artifact`/`read_artifact_slice` should be used for targeted recovery rather than full artifact rereads. Artifact search is historical context and should not be treated as proof of current UI state without a fresh tool observation.
- Runtime instructions tell the agent to treat inferred FSQ preconditions as conditional setup obligations. It must inspect live UI/account state first, execute missing setup before ordered key actions, use `get_runtime_secret` only for configured secret names when credentials are required, and never echo secret values in progress events, evidence, or final output.
- Runtime instructions and task input are assembled by first building prompt models, then rendering Jinja template files configured by `openai_agents.prompt.agent_template_path` and `openai_agents.prompt.task_template_path` or the package defaults. Static behavioral prompt text and section wording belong in template files, while configuration injects only custom instructions, variables, and optional template paths.
- If the user description is too broad to derive domain-specific checks, the default success standard is that the executable task flow completes without unrecovered errors and with enough evidence to show completion.
- Skills are descriptive guidance. Command execution is not exposed through configured CLI tools or SDK `ShellTool` in this SPEC cycle; execution is performed through harness platform tools and CommonTool utilities only.
- Harness- and platform-specific action selection, argument rules, and recovery recipes belong in configured skill Markdown rather than hard-coded agent runtime branches. The agent consumes those skills as current runtime policy while remaining decoupled from concrete platform backends.
- The final SDK output must conform to `AgentFinalOutput`. `AgentFinalOutput` is passed to OpenAI Agents SDK through `Agent(output_type=AgentFinalOutput)`, and its JSON Schema is rendered into the prompt for model-visible contract guidance.
- Final output includes `schema_version` for traceability. Schema selection is not configurable; the runtime owns the current contract.
- The runtime converts `pre_plan` entries from typed final output into `StepResult` records, then appends one SDK runner summary step containing the serialized final output.
- Task input is rendered from an `AgentTaskInput` model so the model-facing task envelope has a stable shape while still allowing template customization.
- SDK stream events are mapped into `RunEvent` values that preserve real tool names, call IDs, redacted arguments, output previews, errors, timing, tool origin when known (`harness`, `common`, `runtime`, or `unknown`), and safe replay/provenance metadata when available. Reports reconstruct real tool calls from these events rather than treating plan or runner summary records as tools. CLI post-run recording may consume the same persisted events, but `agent` does not decide recording eligibility or write generated case files.
- Task execution is non-interactive. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Final result judgment is performed by a separate evidence-based verification agent task after the main automation run. The verification task has no harness action tools, no CommonTool action tools, and no image inputs; it receives the authoritative task/case intent, the main agent's structured claims when available, execution records, normalized event/tool-call records, AI assertion verdict metadata, and persisted artifact excerpts. The verification agent must decide success, failure, or inconclusive from supplied execution evidence only.
- Final verification applies `verification.mode` after the main automation run. In `strict` mode, success requires the goal plus all required assertion and operation criteria. In `normal` mode, success requires the goal plus required assertion criteria, while operation criteria are retained as evidence and diagnostics but do not block success. In `goal` mode, success requires only goal criteria. A criterion excluded by mode must not appear as an unmet blocking criterion in the final `VerificationResult`.
- Visual assertions in the LLM execution loop are judged during the main execution loop when the agent explicitly calls a harness-owned platform assertion such as `assert_with_ai` and receives the provider-backed verdict as tool output evidence. The verification task does not re-inspect screenshot pixels; it verifies that execution evidence contains the platform AI assertion result, that the main agent's structured output reports the corresponding result, and that no supplied evidence contradicts that result.
- Deterministic strict-core execution is not an agent capability. Strict entry-layer code may inject a provider-backed evaluator for explicitly authored `assertWithAI`, but `agent` does not own strict execution or construct strict harnesses.
- Dynamic run recording is not an agent capability. `agent` must persist safe event metadata needed by `cli` recording, but must not write `recorded.codex.yaml`, mutate source cases, resolve strict replay refs, or decide whether a run should be recorded.
- The local `Verifier` does not hard-code FSQ key-action formats or Appium command semantics as the final arbiter. It treats a parseable verification-agent status as authoritative, preserving the agent's success, failed, or inconclusive conclusion without local status downgrades. If the verification task is unavailable, it uses parseable runner output as the fallback conclusion; if no agent conclusion is parseable, it falls back to failed-step or inconclusive diagnostics.
