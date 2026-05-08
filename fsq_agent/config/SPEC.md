# Module: config

## Purpose

Load, merge, normalize, and validate runtime configuration for the OpenAI Agents SDK runtime, Azure OpenAI model deployment, MCP servers, MCP tool validation policy, CLI tools, automation skills, observation settings, case input directories, the fsq-agent workspace, and output directories.

## Dependencies

- `models`: Uses `AgentSettings`, `OpenAIAgentsSettings`, `MCPServerConfig`, `MCPToolValidationSettings`, `WorkspaceSettings`, `CaseSettings`, `CLIToolConfig`, `ShellSettings`, `SkillConfig`, `ObservationSettings`, `OutputSettings`, and `ConfigurationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `Settings`: Runtime settings aggregate model that combines agent, OpenAI Agents SDK provider, MCP, MCP tool validation, workspace, case directory, CLI, shell, skills, observation, and output configuration.
- `load_settings(path: str | Path | None = None, workspace: str | Path | None = None) -> Settings`: Loads `.env` values without overriding existing environment variables, then loads YAML configuration from the provided path or default search locations. The optional workspace argument overrides `workspace.root_dir`.
- `resolve_runtime_paths(settings: Settings, base_dir: Path | None = None) -> None`: Ensures the fsq-agent workspace is initialized and marked, resolves case and knowledge directories, and creates output directories under the workspace.
- `validate_runtime_settings(settings: Settings) -> None`: Validates that OpenAI Agents SDK is enabled, secrets are present, Azure OpenAI base URL shape is valid, model deployment name is configured, optional shell policy is valid, and local path constraints pass before a run starts.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML loading, environment variable handling, default path discovery, endpoint normalization, and runtime validation.
- `_settings.py`: `Settings` aggregate model.
- `_paths.py`: Workspace marker validation and runtime path resolution helpers.
- `SPEC.md`: Module design.

## Error Handling

Invalid or missing configuration raises `ConfigurationError` from `models`. Low-level YAML, path, workspace marker, or validation exceptions are wrapped with actionable context.

## Design Decisions

- Configuration is read once during application startup and passed into modules explicitly.
- fsq-agent never writes runtime artifacts relative to the caller's current directory. A configured or default workspace is initialized with `.fsq-agent-workspace`; non-empty unmarked directories are rejected to avoid treating a public user directory as a managed workspace.
- Relative `cases.dir` and `knowledge_dir` values resolve relative to the configuration file directory. Relative `output.root_dir` and `shell.working_dir` values resolve inside the fsq-agent workspace.
- The API key is never stored in config files. `openai_agents.api_key_env` names an environment variable such as `AZURE_OPENAI_API_KEY`, which can be provided by a local `.env` file ignored by git.
- Azure OpenAI endpoints are normalized to the OpenAI-compatible Responses base URL form, for example `https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/`.
- The default model is the Azure deployment name `gpt-5.4`, not an OpenAI public model alias.
- Non-interactive execution is the default: trusted MCP servers use `require_approval: never`; any approval callback must be programmatic.
- Local shell execution is disabled by default. When enabled, `shell.mode: allowlist` requires `command_allowlist`; `shell.mode: allow_all` intentionally permits unrestricted local shell commands inside the fsq-agent workspace.
- Output directory creation is part of config resolution so later modules can assume directories are writable. Reports, logs, traces, screenshots, and generated files must be placed under `output.root_dir`; completed run reports are stored under `output.runs_dir`.
- MCP tool validation is enabled by default and uses `auto_ignore` policy so a single malformed MCP tool schema does not prevent otherwise healthy tools on the same server from being registered with the OpenAI Agents SDK.