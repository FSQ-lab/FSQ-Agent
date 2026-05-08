# Module: agent

## Purpose

Coordinate the goal-driven testing workflow using OpenAI Agents SDK: load runtime settings, build the Azure OpenAI-backed agent, attach configured tools and MCP servers, load relevant knowledge, flow templates, and skills, derive acceptance criteria when the user only provides a task description, generate a task pre-plan with success criteria, execute and dynamically adjust that pre-plan through SDK-managed tool calls, derive verification status from structured final output, and trigger report generation.

## Dependencies

- `models`: Uses all task, plan, result, tool, report, and exception models.
- `config`: Uses runtime settings.
- `tools`: Builds OpenAI Agents SDK tools/MCP servers and exposes diagnostic capabilities.
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
- `FsqAgent.run(task: Task) -> TaskResult`
- `OpenAIAgentsRuntime.run_task(task: Task) -> list[StepResult]`
- `Verifier.verify(task: Task, results: list[StepResult]) -> VerificationResult`

## Internal Structure

- `__init__.py`: Public exports only.
- `_core.py`: `FsqAgent` orchestration and lifecycle.
- `_openai_runtime.py`: OpenAI Agents SDK client/provider setup, agent construction, MCP context management, MCP validation diagnostic step injection, and `Runner.run` invocation.
- `_structured_output.py`: Shared parser for the SDK final JSON contract and helpers for structured list fields.
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
- The agent must create a pre-plan before external actions, derive task success criteria from the description, private knowledge, flow templates, and skills when the user did not provide criteria, include those criteria in the pre-plan, execute through MCP/tools/skills, and adapt the plan when tool feedback changes the best path.
- If the user description is too broad to derive domain-specific checks, the default success standard is that the executable task flow completes without unrecovered errors and with enough evidence to show completion.
- Skills are descriptive guidance. Command execution is performed only through configured CLI tools, MCP tools, or optional SDK `ShellTool` governed by `ShellSettings`.
- The final SDK output must be JSON containing `status`, `summary`, `pre_plan`, `plan_updates`, `satisfied_criteria`, `unmet_criteria`, `evidence`, and `errors`.
- The runtime converts `pre_plan` entries from final JSON into `StepResult` records, then appends one SDK runner summary step containing the raw final output.
- MCP tool validation diagnostics from startup filtering are prepended as skipped diagnostic `StepResult` records so generated reports explain any automatically ignored tools.
- Task execution is non-interactive. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- The verifier is independent from the runtime prompt to reduce confirmation bias between intended goal and actual outcome.
