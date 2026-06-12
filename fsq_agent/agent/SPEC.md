# Module: agent

## Purpose

Coordinate the goal-driven testing workflow using OpenAI Agents SDK: load runtime settings, construct or receive the configured harness, build the OpenAI-compatible agent, attach local utility tools and harness-generated platform action tools, load relevant knowledge and skills, derive execution and verification context when the user only provides a task description, generate a task pre-plan with success criteria, execute and dynamically adjust that pre-plan through SDK-managed tool calls, derive verification status from structured final output according to configured verification mode, and trigger report generation.

## Dependencies

- `models`: Uses all task, plan, structured agent IO, result, tool, report, event, and exception models.
- `config`: Uses runtime settings.
- `core`: Uses `HarnessInterface` implementations and shared harness behavior through public core exports supplied by entry/runtime construction.
- `tools`: Builds local OpenAI Agents SDK utility tools and exposes diagnostic capabilities.
- `observation`: Captures evidence after steps.
- `knowledge`: Loads private knowledge.
- `skills`: Loads configured automation skill instruction bundles.
- `report`: Generates reports and evidence bundles.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `FsqAgent`: Main orchestration class.
- `OpenAIAgentsRuntime`: Builds and runs an OpenAI Agents SDK `Agent` with Azure OpenAI or GitHub Copilot provider configuration, local utility tools, harness-generated platform action tools, skills, turn limits, and tracing policy.
- `OpenAIAssertionEvaluator`: Synchronous evaluator for authored core `assertWithAI` steps. It uses the configured OpenAI-compatible provider directly, receives screenshot bytes and UI-tree context from a harness, and returns a structured visual assertion verdict without owning platform execution.
- `GoalPrePlanner`: Uses the OpenAI Agents SDK with read-only knowledge lookup tools to convert a natural-language goal plus page knowledge into an ordered key-action pre-plan.
- `Verifier`: Parses structured verifier-agent or runner final output and converts task status, satisfied criteria, unmet criteria, evidence, diagnostics, and configured verification mode into a `VerificationResult`.

Planned signatures:

- `FsqAgent.from_config(path: str | Path | None = None, workspace: str | Path | None = None) -> FsqAgent`
- `FsqAgent.from_settings(settings: Settings) -> FsqAgent`
- `FsqAgent.run(task: Task, event_sink: RunEventSink | None = None) -> TaskResult`
- `FsqAgent.pre_plan_goal(goal: str, event_sink: RunEventSink | None = None) -> GoalPrePlan`
- `OpenAIAgentsRuntime.run_task(task: Task, knowledge: KnowledgeBundle, skills: list[SkillBundle], run_id: str, event_sink: RunEventSink | None = None) -> list[StepResult]`
- `OpenAIAgentsRuntime.run_pre_plan(goal: str, knowledge: KnowledgeBundle, skills: list[SkillBundle], run_id: str, event_sink: RunEventSink | None = None) -> GoalPrePlan`
- `OpenAIAssertionEvaluator(settings: Settings).evaluate(prompt: str, screenshot: bytes, ui_tree: dict[str, object] | None, metadata: dict[str, object]) -> dict[str, object]`
- `Verifier.verify(task: Task, results: list[StepResult], events_path: Path | None = None, mode: VerificationMode = "normal") -> VerificationResult`

## Internal Structure

- `__init__.py`: Public exports only.
- `_core.py`: `FsqAgent` orchestration and lifecycle.
- `_events.py`: Run event emission, sequencing, persistence fan-out, and user-sink dispatch.
- `_openai_runtime.py`: OpenAI Agents SDK client/provider setup, harness construction or injection, local and harness tool assembly, agent construction, `Runner.run_streamed` invocation, and SDK stream event mapping.
- Future `_harness_tools.py`: Harness `FunctionTool` adapter that converts `HarnessFunctionSchema` records into SDK tools, maps SDK tool arguments into `ExecutableStep` records, invokes `HarnessInterface`, and serializes `HarnessActionResult` records to bounded model-visible JSON.
- `_ai_assertion.py`: OpenAI-compatible visual assertion evaluator used by strict core entrypoints only when explicitly enabled.
- `_pre_plan.py`: Prompt instructions and helpers for goal-only pre-planning from page knowledge.
- `_prompt.py`: Prompt model construction and template rendering for agent instructions and task input.
- `_structured_output.py`: Shared coercion helpers for SDK final output values and compatibility parsing of legacy/raw final JSON strings.
- `_verification_task.py`: Builds an evidence bundle from task context, execution records, event logs, and persisted tool artifacts for a separate evidence-based verification agent task.
- `_verifier.py`: Acceptance criteria verification and failure diagnostics.
- `SPEC.md`: Module design.

## Error Handling

Configuration errors are raised before task execution when OpenAI Agents SDK is disabled, required provider credentials are absent, harness construction fails, or harness action-space conversion fails. SDK, harness, or local tool runtime exceptions are converted into failed `StepResult` values so report generation can still complete. Recoverable tool failures should be surfaced through structured final JSON. Verification treats invalid final JSON as inconclusive instead of claiming task success.

Goal pre-planning raises configuration errors when OpenAI Agents SDK configuration is unavailable and planning errors when the SDK does not return a valid `GoalPrePlan`. Pre-planning does not construct platform harnesses, call UI/external action tools, or generate reports. Read-only knowledge lookup tool failures are surfaced to the planner as warnings so it can continue when possible.

During `FsqAgent.run`, a task with no ordered key actions is treated as a goal-only task. Before external UI actions begin, the orchestrator runs the existing goal pre-planner with the task goal, converts returned `GoalKeyAction` values into `Task.key_actions`, emits planning events on the same run timeline, and then executes the normal task runtime. If the pre-plan returns no key actions, execution still proceeds with the original goal-only task and a warning event; if pre-planning raises an error, the task run fails before external actions are attempted.

## Design Decisions

- The orchestration module depends on all leaf modules, but leaf modules never depend on `agent`.
- OpenAI Agents SDK is the selected agent runtime and tool-use integration layer for this project.
- Azure OpenAI is accessed through an OpenAI-compatible `AsyncOpenAI` client or `OpenAIProvider` using a normalized `/openai/v1/` base URL and deployment name such as `gpt-5.4`. GitHub Copilot provider mode uses the same OpenAI Agents SDK `OpenAIProvider` abstraction, but builds the underlying `AsyncOpenAI` client from GitHub device-code/OAuth credentials, a short-lived Copilot API token, required Copilot headers, and a plan-specific Copilot API base URL. All configured model providers use the Responses API; GitHub Copilot mode is validated with Copilot model `gpt-5.5`.
- Task execution requires the OpenAI Agents SDK package and provider authentication to be available. Azure OpenAI requires the configured API key environment variable. GitHub Copilot runs GitHub device-code authentication on first use, caches the OAuth token under the resolved fsq-agent workspace, reuses unexpired cached authorization, and reauthorizes when the cached token is expired. There is no offline fallback execution path.
- The SDK runner owns tool dispatch and turn continuation. The project should not reimplement the Responses function-call loop.
- Platform action tools are generated from the active harness. `OpenAIAgentsRuntime` reads `HarnessInterface.action_space()`, converts each `HarnessFunctionSchema` into one SDK `FunctionTool`, and creates SDK agents with no external platform tool servers.
- The harness tool adapter must preserve schema provenance, including platform, driver method, and optional `fsq_action_name`, in run events and tool result metadata.
- When the SDK calls a harness tool, the adapter parses JSON arguments, builds an `ExecutableStep`, calls `harness.get_context()`, invokes `harness.invoke_action(step, context)`, and returns compact JSON derived from `HarnessActionResult`.
- A harness action failure should normally be returned as a successful SDK tool transport result whose JSON has `status="failed"`, `failure_category`, `error_message`, output preview, and artifact refs. Unexpected adapter failures are converted into structured failed tool JSON or failed `StepResult` records depending on when they occur.
- Harness action-space discovery or SDK tool conversion failures are startup configuration errors. The runtime must not silently expose a partial harness action list.
- The agent must create a pre-plan before external actions, derive task success criteria from the description, private knowledge, and skills when the user did not provide criteria, include those criteria in the pre-plan, execute through harness and local utility tools, and adapt the plan when tool feedback changes the best path.
- Goal pre-planning is an explicit standalone capability used before execution integration. It receives only a goal string, loads the concise page index from `pre_plan.knowledge_dir` when configured or from `knowledge_dir` as a fallback, and returns ordered key actions plus relevant page ids. It is intentionally side-effect-free for the application under test: no UI automation, no lifecycle calls, no verification agent, and no report generation.
- Integrated goal-only execution reuses the same pre-planning capability, but it is scoped to the task run rather than a separate `pre-plan-*` run. Generated key actions become the execution spine only; final verification remains governed by the task's goal-level criteria and configured verification mode.
- Pre-planning is an iterative knowledge loop. The initial model input contains `index.md` only. The pre-plan agent can call read-only local knowledge tools to reload the index or load specific page files from `knowledge/pages/` by page id or relative path. Page-to-page transitions may cause additional page reads until the action chain is complete or no useful next page is available.
- If page knowledge is incomplete, the planner should still produce the best available contiguous key-action chain. It may skip at most one consecutive missing action by recording a warning. If it cannot produce a useful plan from the available graph, it must return a valid `GoalPrePlan` with an empty `key_actions` list.
- When FSQ task input provides ordered key actions, the pre-plan must use the complete list as the execution spine regardless of final verification mode: preserve their relative order, allow recovery/setup/dialog-handling steps between them, and collect live evidence for the resulting state before reporting success.
- Ordered key actions must preserve semantic fidelity. Recovery or fallback actions may restore UI state, but they do not satisfy the original ordered key action unless they perform the same accepted semantic action. Tool usage errors should be corrected for the same semantic action before switching to non-equivalent fallback routes.
- Run identifiers are generated by the orchestration layer as `<task-id>-YYYY-MM-DD_HH-MM-SS` using local time so directories under `output.runs_dir` are easy to read while remaining path-safe on Windows.
- Task runs emit live `RunEvent` values for planning summaries, harness/local SDK tool calls, tool outputs, failures, and completion. Events are for user-visible progress and must not expose hidden model chain-of-thought. Runtime interruptions such as debugger cancellation or keyboard interrupt emit a final `run_failed` event before being re-raised.
- The runtime consumes OpenAI Agents SDK streaming semantic events through `Runner.run_streamed(...).stream_events()` and maps them into `RunEvent` values while preserving the final output path used by verification and reporting.
- The runtime configures the OpenAI Agents SDK `call_model_input_filter` with `ToolOutputTrimmer` plus a project filter that preserves the most recent configured number of function tool outputs by tool-call count. This keeps recent outputs at full fidelity while trimming older large tool outputs before each model call.
- The project filter persists SDK function-call outputs, including harness and local utility outputs when represented as function-call output items, into the current run's tool artifact directory before replacing historical oversized content with a bounded preview and artifact path.
- The project filter converts readable screenshots into model-visible image inputs for the main runner only after the agent explicitly calls the local `submit_visual_assertion` tool. Routine screenshots remain text evidence and do not trigger image attachment. This lets the execution agent inspect the exact screenshot it binds to visual assertions such as `assertWithAI`; screenshot paths outside the output root, unreadable files, or unsupported image extensions are ignored.
- Runtime instructions tell the agent that local tool outputs may include artifact references and that `search_artifact`/`read_artifact_slice` should be used for targeted recovery rather than full artifact rereads. Artifact search is historical context and should not be treated as proof of current UI state without a fresh tool observation.
- Runtime instructions tell the agent to treat inferred FSQ preconditions as conditional setup obligations. It must inspect live UI/account state first, execute missing setup before ordered key actions, use `get_runtime_secret` only for configured secret names when credentials are required, and never echo secret values in progress updates, evidence, or final output.
- Runtime instructions and task input are assembled by first building prompt models, then rendering Jinja template files configured by `openai_agents.prompt.agent_template_path` and `openai_agents.prompt.task_template_path` or the package defaults. Static behavioral prompt text and section wording belong in template files, while configuration injects only custom instructions, variables, and optional template paths.
- If the user description is too broad to derive domain-specific checks, the default success standard is that the executable task flow completes without unrecovered errors and with enough evidence to show completion.
- Skills are descriptive guidance. Command execution is performed only through configured CLI tools, harness tools, local utility tools, or optional SDK `ShellTool` governed by `ShellSettings`.
- Harness- and platform-specific action selection, argument rules, and recovery recipes belong in configured skill Markdown rather than hard-coded agent runtime branches. The agent consumes those skills as current runtime policy while remaining decoupled from concrete platform backends.
- The final SDK output must conform to `AgentFinalOutput`. `AgentFinalOutput` is passed to OpenAI Agents SDK through `Agent(output_type=AgentFinalOutput)`, and its JSON Schema is rendered into the prompt for model-visible contract guidance.
- Final output includes `schema_version` for traceability. Schema selection is not configurable; the runtime owns the current contract.
- The runtime converts `pre_plan` entries from typed final output into `StepResult` records, then appends one SDK runner summary step containing the serialized final output.
- Task input is rendered from an `AgentTaskInput` model so the model-facing task envelope has a stable shape while still allowing template customization.
- SDK stream events are mapped into `RunEvent` values that preserve real tool names, call IDs, redacted arguments, output previews, errors, timing, and tool origin when known. Reports reconstruct real tool calls from these events rather than treating plan or runner summary records as tools.
- Task execution is non-interactive. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Final result judgment is performed by a separate evidence-based verification agent task after the main automation run. The verification task has no harness action tools, no local action tools, and no image inputs; it receives the authoritative task/case intent, the main agent's structured claims when available, execution records, normalized event/tool-call records, and persisted artifact excerpts. The verification agent must decide success, failure, or inconclusive from supplied execution evidence only.
- Final verification applies `verification.mode` after the main automation run. In `strict` mode, success requires the goal plus all required assertion and operation criteria. In `normal` mode, success requires the goal plus required assertion criteria, while operation criteria are retained as evidence and diagnostics but do not block success. In `goal` mode, success requires only goal criteria. A criterion excluded by mode must not appear as an unmet blocking criterion in the final `VerificationResult`.
- Visual assertions such as FSQ `assertWithAI` are judged during the main execution loop: the runner captures a screenshot, calls `submit_visual_assertion`, and receives the screenshot as a model-visible image on the next model turn. The verification task does not re-inspect screenshot pixels. It verifies that the execution stage completed the visual assertion submission, that the main agent's structured output reports the corresponding visual assertion result, and that no supplied evidence contradicts that result.
- In deterministic strict-core execution, authored `assertWithAI` steps use `OpenAIAssertionEvaluator` only when the entrypoint explicitly enables AI assertions. The evaluator is injected into `AndroidHarness` from the CLI/entry layer, not from `core`. It must return one of `passed`, `failed`, or `inconclusive` plus concise reasoning, and must not perform locator fallback, action repair, testcase mutation, or case-level recovery.
- The local `Verifier` does not hard-code FSQ key-action formats or Appium command semantics as the final arbiter. It treats a parseable verification-agent status as authoritative, preserving the agent's success, failed, or inconclusive conclusion without local status downgrades. If the verification task is unavailable, it uses parseable runner output as the fallback conclusion; if no agent conclusion is parseable, it falls back to failed-step or inconclusive diagnostics.
