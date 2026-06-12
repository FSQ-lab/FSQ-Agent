# Module: config

## Purpose

Load, merge, normalize, and validate runtime configuration for the OpenAI Agents SDK runtime, shared model provider selection, Azure OpenAI model deployment, GitHub Copilot local provider authentication, final verification policy, harness/driver construction, strict-core Android execution, CommonTool safety policy, automation skills, runtime secret allowlists, case input directories, internal goal-planning page knowledge, the fsq-agent workspace, and output directories.

## Dependencies

- `models`: Uses `AgentSettings`, `OpenAIAgentsSettings`, `RuntimeSecretSettings`, `VerificationSettings`, `HarnessSettings`, `AndroidHarnessSettings`, `WorkspaceSettings`, `CaseSettings`, `SkillConfig`, `OutputSettings`, `PrePlanSettings`, `LocalToolOutputSettings`, and `ConfigurationError`.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `Settings`: Runtime settings aggregate model that combines agent, OpenAI Agents SDK provider selection, configurable prompt text, context trimming, CommonTool output artifact policy, harness/driver construction, strict-core Android execution settings, final verification policy, runtime secret allowlists, workspace, case directory, skills, output, normal task knowledge, and internal goal-planning page knowledge configuration.
- `load_settings(path: str | Path | None = None, workspace: str | Path | None = None) -> Settings`: Loads `.env` values without overriding existing environment variables, then loads YAML configuration from the provided path or default search locations. The optional workspace argument overrides `workspace.root_dir`.
- `resolve_runtime_paths(settings: Settings, base_dir: Path | None = None) -> None`: Ensures the fsq-agent workspace is initialized and marked, resolves case and knowledge directories, and creates output directories under the workspace.
- `validate_runtime_settings(settings: Settings) -> None`: Validates provider-specific secrets or auth requirements, Azure OpenAI base URL shape when selected, model deployment name, LLM harness/driver settings, CommonTool policy, and local path constraints before a default LLM run starts.
- `validate_strict_core_settings(settings: Settings, requires_ai_assertion: bool = False) -> None`: Validates strict-core harness/driver settings and mode-level settings not provided by a case file. It does not require provider credentials unless the caller knows the strict run contains an authored `assertWithAI` step or otherwise requires a provider-backed AI assertion evaluator.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML loading, environment variable handling, default path discovery, provider-specific endpoint normalization, and runtime validation.
- `_settings.py`: `Settings` aggregate model.
- `_paths.py`: Workspace marker validation and runtime path resolution helpers.
- `SPEC.md`: Module design.

## Error Handling

Invalid or missing configuration raises `ConfigurationError` from `models`. Low-level YAML, path, workspace marker, or validation exceptions are wrapped with actionable context.

## Design Decisions

- Configuration is read once during application startup and passed into modules explicitly.
- fsq-agent never writes runtime artifacts relative to the caller's current directory. A configured or default workspace is initialized with `.fsq-agent-workspace`; non-empty unmarked directories are rejected to avoid treating a public user directory as a managed workspace.
- Relative `cases.dir`, `knowledge_dir`, and `pre_plan.knowledge_dir` values resolve relative to the configuration file directory. Relative `output.root_dir` values resolve inside the fsq-agent workspace.
- `knowledge_dir` is the normal task private knowledge root. `pre_plan.knowledge_dir` optionally points internal dynamic goal planning at a reusable page-knowledge graph; when omitted, internal planning falls back to `knowledge_dir` for backward compatibility.
- The API key is never stored in config files. For `provider: azure_openai`, `openai_agents.api_key_env` names an environment variable such as `AZURE_OPENAI_API_KEY`, which can be provided by a local `.env` file ignored by git. For `provider: github_copilot`, runtime device-code authentication is used on first run and the GitHub OAuth token is cached under `workspace.root_dir/auth/github-copilot-token.json`; no GitHub token value or token environment variable is configured in YAML.
- Test credentials and other runtime-only secret values are never stored in FSQ case YAML or code. The `runtime_secrets.allowed_env_names` allowlist names the environment variables that the local `get_runtime_secret` tool may return to the model, with values loaded from the process environment or `.env` using the normal loader.
- Azure OpenAI endpoints are normalized to the OpenAI-compatible Responses base URL form, for example `https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/`. GitHub Copilot provider mode does not use the configured Azure base URL; the runtime detects the user's Copilot plan and selects the matching Copilot API endpoint.
- `openai_agents.provider` selects the shared model provider. The default `azure_openai` preserves existing behavior and uses the OpenAI Responses API through the Agents SDK provider. `github_copilot` uses GitHub Copilot subscription-backed access, reads cached workspace authorization when present and unexpired, re-runs device-code authorization when absent or expired, and uses the Responses API with Copilot model `gpt-5.5`. Provider construction and token exchange are implemented by `providers`, not by `config`.
- The default model is the Azure deployment name `gpt-5.4`, not an OpenAI public model alias.
- GPT-5.4 is treated as the default sizing target for tool-output context policy. The default keeps recent moderate CommonTool and harness outputs inline, writes every CommonTool output to a per-run artifact, and trims older large SDK tool outputs before model calls.
- `openai_agents.prompt` owns prompt customization. `prompt.agent_template_path`, `prompt.task_template_path`, and `prompt.custom_instructions_path` may point to files resolved relative to the configuration file directory; when template paths are omitted, package default templates are used. Static prompt text, headings, loops, and task formatting live in templates. Long operator guidance should live in `prompt.custom_instructions_path`; `prompt.custom_instructions` remains available for short inline overrides, and `prompt.variables` provides operator-controlled scalar model data injected into templates.
- `harness.platform` selects the platform harness used by goal-driven task execution. The first supported platform is `android`.
- `harness.android.backend` selects the Android backend. The first supported backend is `uiautomator2`.
- `harness.android.app_id` optionally supplies the Android application id for dynamic LLM runs and strict-core runs. Strict-core may fall back to `appId` from parsed FSQ case metadata when the config value is absent. There are no public CLI app-id overrides.
- `harness.android.serial` optionally selects the Android device serial passed to the uiautomator2 backend.
- Strict-core execution remains deterministic except for explicitly authored `assertWithAI` assertion steps. When a strict run contains `assertWithAI`, entry-layer code may request provider validation and inject a provider-backed evaluator into the platform harness. Missing provider readiness for such a step is a configuration failure. No AI recovery, locator fallback, or testcase mutation is enabled by this setting.
- `verification.mode` selects final verification strictness. The default `normal` verifies the goal and assertion-style criteria. `strict` verifies the goal plus all required ordered key actions, including operation-style criteria. `goal` verifies only the goal-level criteria. The setting affects final verification only; the execution agent still receives all key actions as task context.
- Non-interactive execution is the default. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Output directory creation is part of config resolution so later modules can assume directories are writable. Reports, run event timelines, CommonTool artifacts, and generated files must be placed under `output.root_dir`; completed run reports are stored under `output.runs_dir`.
- Platform action schemas are not configured through external tool servers. They are discovered from the active harness through `HarnessInterface.action_space()` and adapted by the agent runtime into SDK `FunctionTool` objects.