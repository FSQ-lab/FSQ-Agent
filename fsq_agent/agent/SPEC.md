# Module: agent

## Purpose

Coordinate the goal-driven testing workflow using OpenAI Agents SDK: load runtime settings, build the Azure OpenAI-backed agent, attach configured tools and MCP servers, load relevant knowledge, flow templates, and skills, derive acceptance criteria when the user only provides a task description, generate a task pre-plan with success criteria, execute and dynamically adjust that pre-plan through SDK-managed tool calls, derive verification status from structured final output, and trigger report generation.

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
- `Verifier`: Parses SDK structured final output and converts task status, satisfied criteria, unmet criteria, evidence, and diagnostics into a `VerificationResult`.

Planned signatures:

- `FsqAgent.from_config(path: str | Path | None = None, workspace: str | Path | None = None) -> FsqAgent`
- `FsqAgent.from_settings(settings: Settings) -> FsqAgent`
- `FsqAgent.run(task: Task, event_sink: RunEventSink | None = None) -> TaskResult`
- `OpenAIAgentsRuntime.run_task(task: Task, knowledge: KnowledgeBundle, skills: list[SkillBundle], run_id: str, event_sink: RunEventSink | None = None) -> list[StepResult]`
- `Verifier.verify(task: Task, results: list[StepResult], events_path: Path | None = None) -> VerificationResult`

## Internal Structure

- `__init__.py`: Public exports only.
- `_core.py`: `FsqAgent` orchestration and lifecycle.
- `_events.py`: Run event emission, sequencing, persistence fan-out, and user-sink dispatch.
- `_openai_runtime.py`: OpenAI Agents SDK client/provider setup, lifecycle setup/teardown invocation, agent construction, MCP context management, MCP validation diagnostic step injection, `Runner.run_streamed` invocation, and SDK stream event mapping.
- `_prompt.py`: Prompt model construction and template rendering for agent instructions and task input.
- `_structured_output.py`: Shared coercion helpers for SDK final output values and compatibility parsing of legacy/raw final JSON strings.
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
- When FSQ task input provides ordered key actions as acceptance criteria, the pre-plan must use them as the validation spine: preserve their relative order, allow recovery/setup/dialog-handling steps between them, and verify them from live evidence before reporting success.
- Ordered key actions must preserve semantic fidelity. Recovery or fallback actions may restore UI state, but they do not satisfy the original ordered key action unless they perform the same accepted semantic action. Tool usage errors should be corrected for the same semantic action before switching to non-equivalent fallback routes.
- Run identifiers are generated by the orchestration layer as `<task-id>-YYYY-MM-DD_HH-MM-SS` using local time so directories under `output.runs_dir` are easy to read while remaining path-safe on Windows.
- Task runs emit live `RunEvent` values for lifecycle, planning summaries, MCP tool listing, SDK tool calls, tool outputs, failures, and completion. Events are for user-visible progress and must not expose hidden model chain-of-thought. Runtime interruptions such as debugger cancellation or keyboard interrupt emit a final `run_failed` event before being re-raised.
- The runtime consumes OpenAI Agents SDK streaming semantic events through `Runner.run_streamed(...).stream_events()` and maps them into `RunEvent` values while preserving the final output path used by verification and reporting.
- The runtime passes `mcp_tool_validation.strict_schema` to the OpenAI Agents SDK MCP `convert_schemas_to_strict` option so strict MCP schema conversion is controlled by configuration.
- The runtime configures the OpenAI Agents SDK `call_model_input_filter` with `ToolOutputTrimmer` plus a project filter that preserves the most recent configured number of function tool outputs by tool-call count. This keeps recent outputs at full fidelity while trimming older large tool outputs before each model call.
- The project filter persists SDK function-call outputs, including MCP/Appium outputs when represented as function-call output items, into the current run's tool artifact directory before replacing historical oversized content with a bounded preview and artifact path.
- Runtime instructions tell the agent that local tool outputs may include artifact references and that `search_artifact`/`read_artifact_slice` should be used for targeted recovery rather than full artifact rereads. Artifact search is historical context and should not be treated as proof of current UI state without a fresh tool observation.
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
- The verifier is independent from the runtime prompt to reduce confirmation bias between intended goal and actual outcome. After task execution, it may run a separate event-based verification pass over recorded tool-call evidence before falling back to the model's structured final output.
