# Module: models

## Purpose

Own all shared data structures, configuration value models, result objects, tool metadata, skill metadata, report metadata, and exception classes used across Auto Test Agent. This module is the only place where cross-module types and custom exceptions are defined.

## Dependencies

No project module dependencies. May depend on external libraries such as `pydantic` and standard library typing modules.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `Task`: Pydantic model describing a natural-language test task, optional metadata, optional user-provided acceptance criteria, retry limits, timeout, and knowledge references. Only `description` is required. When no acceptance criteria are supplied, the OpenAI Agents SDK runtime must derive them from the task description, knowledge, skills, and flow templates.
- `FsqCaseConfig`: Pydantic model describing the metadata document from an FSQ AI Test DSL `.codex.yaml` case.
- `FsqCase`: Pydantic model containing an FSQ case path, parsed metadata, and command list.
- `ExecutionPlan`: Pydantic model containing ordered `ExecutionStep` items and planning rationale.
- `ExecutionStep`: Pydantic model for one planned tool action with expected outcome and retry policy.
- `StepResult`: Pydantic model for one executed, skipped, failed, or adjusted pre-plan step outcome, timings, evidence references, and error summary.
- `VerificationResult`: Pydantic model describing whether the task goal was achieved and why.
- `TaskResult`: Pydantic model returned by the agent after execution, verification, and report generation.
- `ReportArtifact`: Pydantic model describing generated report paths and evidence bundle paths.
- `KnowledgeBundle`: Pydantic model containing loaded private knowledge, matched flow templates, and warnings for agent context.
- `ToolDefinition`: Pydantic model describing a discovered MCP, CLI, or file operation capability.
- `ToolCall`: Pydantic model describing a tool invocation request.
- `ToolResult`: Pydantic model describing a normalized tool invocation response.
- `OpenAIAgentsSettings`: Pydantic model for OpenAI Agents SDK provider configuration, including Azure OpenAI base URL, API key environment variable, model deployment name, tracing policy, turn limits, and Responses API options.
- `MCPServerConfig`: Pydantic model for OpenAI Agents SDK MCP configuration. Supports `stdio`, `streamable_http`, `sse`, and `hosted` transports plus approval policy, headers, tool filters, and prompt loading policy.
- `CLIToolConfig`: Pydantic model for configured CLI tools.
- `SkillConfig`: Pydantic model for one configured automation skill source.
- `SkillBundle`: Pydantic model containing loaded skill instructions, optional files, descriptions, and warnings.
- `AgentSettings`: Pydantic model for model name, step limits, timeouts, and retry defaults.
- `ShellSettings`: Pydantic model for optional SDK `ShellTool` execution, including disabled-by-default local shell execution, `allowlist` mode, explicit high-trust `allow_all` mode, timeout, and working directory.
- `ObservationSettings`: Pydantic model for screenshot, UI tree, and logging configuration.
- `OutputSettings`: Pydantic model for logs, reports, screenshots, and trace directories.
- `AutoTestAgentError`: Base exception for all project errors.
- `ConfigurationError`: Raised when configuration is missing or invalid.
- `PlanningError`: Raised when a task cannot be converted into an executable plan.
- `ToolExecutionError`: Raised when a tool call fails after retries or returns invalid output.
- `ObservationError`: Raised when evidence capture fails unexpectedly.
- `VerificationError`: Raised when verification cannot complete.
- `ReportGenerationError`: Raised when report generation fails.

## Internal Structure

- `__init__.py`: Public exports only.
- `_task.py`: Task, plan, step, result, and verification models.
- `_fsq.py`: FSQ AI Test DSL case metadata and case models.
- `_tools.py`: Tool metadata, tool call, tool result, MCP and CLI config models.
- `_settings.py`: Settings value models.
- `_skills.py`: Skill configuration and loaded skill bundle models.
- `_report.py`: Report artifact and evidence models.
- `_knowledge.py`: Knowledge bundle model.
- `_exceptions.py`: Shared exception hierarchy.
- `SPEC.md`: Module design.

## Error Handling

All custom exceptions inherit from `AutoTestAgentError`. Exceptions carry concise human-readable messages and optional structured context fields where useful. Other modules must import exception classes from this module rather than defining their own.

## Design Decisions

- Centralizing types prevents circular imports and inconsistent result schemas.
- Pydantic is used at boundaries where external inputs, config files, agent output, and tool output enter the system.
- Result models store evidence paths rather than binary evidence to keep logs and reports lightweight.
- OpenAI Agents SDK runtime objects are not stored directly in shared models. Models hold serializable configuration that `agent` and `tools` adapt into SDK `Agent`, `FunctionTool`, `MCPServer*`, and hosted tool objects.
- Skills are descriptive instruction bundles. CLI/shell execution is controlled separately by configured CLI tools or `ShellSettings`.
- FSQ `.codex.yaml` cases are converted into `Task` descriptions for the agent loop. The parsed FSQ models preserve source metadata and command flow before rendering.
