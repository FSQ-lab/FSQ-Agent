# Module: agent

## Purpose

Coordinate the goal-driven testing workflow using OpenAI Agents SDK: load runtime settings, build the Azure OpenAI-backed agent, attach configured tools and MCP servers, load relevant knowledge, flow templates, and skills, derive execution and verification context when the user only provides a task description, generate a task pre-plan with success criteria, execute and dynamically adjust that pre-plan through SDK-managed tool calls, derive verification status from structured final output according to configured verification mode, and trigger report generation.

## Dependencies

- `models`: Uses all task, plan, structured agent IO, result, tool, report, event, and exception models.
- `config`: Uses runtime settings.
- `tools`: Builds OpenAI Agents SDK tools/MCP servers, lifecycle controllers, and exposes diagnostic capabilities.
- `observation`: Captures evidence after steps.
- `knowledge`: Loads private knowledge and flow templates.
- `skills`: Loads configured automation skill instruction bundles.
- `report`: Generates reports and evidence bundles.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `FsqAgent`: Main orchestration class.
- `OpenAIAgentsRuntime`: Builds and runs an OpenAI Agents SDK `Agent` with Azure OpenAI configuration, tools, MCP servers, skills, turn limits, and tracing policy.
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
- `_openai_runtime.py`: OpenAI Agents SDK client/provider setup, lifecycle setup/teardown invocation, agent construction, MCP context management, MCP validation diagnostic step injection, `Runner.run_streamed` invocation, and SDK stream event mapping.
- `_prompt.py`: Prompt model construction and template rendering for agent instructions and task input.
- `_structured_output.py`: Shared coercion helpers for SDK final output values and compatibility parsing of legacy/raw final JSON strings.
- `_verification_task.py`: Builds an evidence bundle from task context, execution records, event logs, and persisted tool artifacts for a separate evidence-based verification agent task.
- `_verifier.py`: Acceptance criteria verification and failure diagnostics.
- `SPEC.md`: Module design.

## Error Handling

Configuration errors are raised before task execution when OpenAI Agents SDK is disabled or required Azure OpenAI credentials are absent. SDK/MCP/tool runtime exceptions are converted into failed `StepResult` values so report generation can still complete. Recoverable tool failures should be surfaced through structured final JSON. Verification treats invalid final JSON as inconclusive instead of claiming task success.

## Design Decisions

- The orchestration module depends on all leaf modules, but leaf modules never depend on `agent`.
- OpenAI Agents SDK is the selected agent runtime and tool-use integration layer for this project.
- Azure OpenAI is accessed through an OpenAI-compatible `AsyncOpenAI` client or `OpenAIProvider` using a normalized `/openai/v1/` base URL and deployment name such as `gpt-5.4`.
- Task execution requires OpenAI Agents SDK to be enabled and the configured Azure OpenAI API key environment variable to be present. There is no offline fallback execution path.
- The SDK runner owns tool dispatch and turn continuation. The project should not reimplement the Responses function-call loop.
- Configured lifecycle controllers may make deterministic setup/teardown MCP calls before and after the model tool loop. Those calls are not agent reasoning steps; they are runtime preparation/cleanup and are emitted as lifecycle-tagged tool-call events.
- The agent must create a pre-plan before external actions, derive task success criteria from the description, private knowledge, flow templates, and skills when the user did not provide criteria, include those criteria in the pre-plan, execute through MCP/tools/skills, and adapt the plan when tool feedback changes the best path.
- When FSQ task input provides ordered key actions, the pre-plan must use the complete list as the execution spine regardless of final verification mode: preserve their relative order, allow recovery/setup/dialog-handling steps between them, and collect live evidence for the resulting state before reporting success.
- Ordered key actions must preserve semantic fidelity. Recovery or fallback actions may restore UI state, but they do not satisfy the original ordered key action unless they perform the same accepted semantic action. Tool usage errors should be corrected for the same semantic action before switching to non-equivalent fallback routes.
- Run identifiers are generated by the orchestration layer as `<task-id>-YYYY-MM-DD_HH-MM-SS` using local time so directories under `output.runs_dir` are easy to read while remaining path-safe on Windows.
- Task runs emit live `RunEvent` values for lifecycle, planning summaries, MCP tool listing, SDK tool calls, tool outputs, failures, and completion. Events are for user-visible progress and must not expose hidden model chain-of-thought. Runtime interruptions such as debugger cancellation or keyboard interrupt emit a final `run_failed` event before being re-raised.
- The runtime consumes OpenAI Agents SDK streaming semantic events through `Runner.run_streamed(...).stream_events()` and maps them into `RunEvent` values while preserving the final output path used by verification and reporting.
- The runtime passes `mcp_tool_validation.strict_schema` to the OpenAI Agents SDK MCP `convert_schemas_to_strict` option so strict MCP schema conversion is controlled by configuration.
- The runtime configures the OpenAI Agents SDK `call_model_input_filter` with `ToolOutputTrimmer` plus a project filter that preserves the most recent configured number of function tool outputs by tool-call count. This keeps recent outputs at full fidelity while trimming older large tool outputs before each model call.
- The project filter persists SDK function-call outputs, including MCP/Appium outputs when represented as function-call output items, into the current run's tool artifact directory before replacing historical oversized content with a bounded preview and artifact path.
- The project filter converts readable screenshots into model-visible image inputs for the main runner only after the agent explicitly calls the local `submit_visual_assertion` tool. Routine screenshots remain text evidence and do not trigger image attachment. This lets the execution agent inspect the exact screenshot it binds to visual assertions such as `assertWithAI`; screenshot paths outside the output root, unreadable files, or unsupported image extensions are ignored.
- Runtime instructions tell the agent that local tool outputs may include artifact references and that `search_artifact`/`read_artifact_slice` should be used for targeted recovery rather than full artifact rereads. Artifact search is historical context and should not be treated as proof of current UI state without a fresh tool observation.
- Runtime instructions tell the agent to treat inferred FSQ preconditions as conditional setup obligations. It must inspect live UI/account state first, execute missing setup before ordered key actions, use `get_runtime_secret` only for configured secret names when credentials are required, and never echo secret values in progress updates, evidence, or final output.
- Runtime instructions and task input are assembled by first building prompt models, then rendering Jinja template files configured by `openai_agents.prompt.agent_template_path` and `openai_agents.prompt.task_template_path` or the package defaults. Static behavioral prompt text and section wording belong in template files, while configuration injects only custom instructions, variables, and optional template paths.
- If the user description is too broad to derive domain-specific checks, the default success standard is that the executable task flow completes without unrecovered errors and with enough evidence to show completion.
- Skills are descriptive guidance. Command execution is performed only through configured CLI tools, MCP tools, or optional SDK `ShellTool` governed by `ShellSettings`.
- MCP-specific tool selection, argument rules, and recovery recipes belong in configured skill Markdown rather than agent runtime branches. The agent consumes those skills as current runtime policy while remaining platform- and MCP-neutral.
- The final SDK output must conform to `AgentFinalOutput`. `AgentFinalOutput` is passed to OpenAI Agents SDK through `Agent(output_type=AgentFinalOutput)`, and its JSON Schema is rendered into the prompt for model-visible contract guidance.
- Final output includes `schema_version` for traceability. Schema selection is not configurable; the runtime owns the current contract.
- The runtime converts `pre_plan` entries from typed final output into `StepResult` records, then appends one SDK runner summary step containing the serialized final output.
- Task input is rendered from an `AgentTaskInput` model so the model-facing task envelope has a stable shape while still allowing template customization.
- SDK stream events are mapped into `RunEvent` values that preserve real tool names, call IDs, redacted arguments, output previews, errors, timing, and tool origin when known. Reports reconstruct real tool calls from these events rather than treating plan or runner summary records as tools.
- MCP tool validation diagnostics from startup filtering are prepended as skipped diagnostic `StepResult` records so generated reports explain any automatically ignored tools.
- Task execution is non-interactive. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Final result judgment is performed by a separate evidence-based verification agent task after the main automation run. The verification task has no MCP servers, no lifecycle controller, no external action tools, and no image inputs; it receives the authoritative task/case intent, the main agent's structured claims when available, execution records, normalized event/tool-call records, and persisted artifact excerpts. The verification agent must decide success, failure, or inconclusive from supplied execution evidence only.
- Final verification applies `verification.mode` after the main automation run. In `strict` mode, success requires the goal plus all required assertion and operation criteria. In `normal` mode, success requires the goal plus required assertion criteria, while operation criteria are retained as evidence and diagnostics but do not block success. In `goal` mode, success requires only goal criteria. A criterion excluded by mode must not appear as an unmet blocking criterion in the final `VerificationResult`.
- Visual assertions such as FSQ `assertWithAI` are judged during the main execution loop: the runner captures a screenshot, calls `submit_visual_assertion`, and receives the screenshot as a model-visible image on the next model turn. The verification task does not re-inspect screenshot pixels. It verifies that the execution stage completed the visual assertion submission, that the main agent's structured output reports the corresponding visual assertion result, and that no supplied evidence contradicts that result.
- The local `Verifier` does not hard-code FSQ key-action formats or Appium command semantics as the final arbiter. It treats a parseable verification-agent status as authoritative, preserving the agent's success, failed, or inconclusive conclusion without local status downgrades. If the verification task is unavailable, it uses parseable runner output as the fallback conclusion; if no agent conclusion is parseable, it falls back to failed-step or inconclusive diagnostics.
