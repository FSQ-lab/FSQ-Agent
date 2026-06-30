# Module: config

## Purpose

Load, merge, normalize, and validate runtime configuration for the OpenAI Agents SDK runtime, shared model provider selection, env-backed Azure OpenAI settings, GitHub Copilot local provider authentication, env-backed Android app/device selection, Web Playwright harness settings, harness/driver/platform tool construction, runner-owned post-action delay defaults, strict-core platform readiness, strict replay secret resolution, AgentTool output policy, platform CommonTool safety policy, agent-context knowledge and skills, prompt template paths and variables, runtime secret allowlists, case input directories, internal goal-planning page knowledge, the fsq-agent workspace, and output directories.

## Dependencies

- `models`: Uses `AgentSettings`, `OpenAIAgentsSettings`, `RuntimeSecretSettings`, `HarnessSettings`, `AndroidHarnessSettings`, `WebHarnessSettings`, `StrictCoreHarnessSettings`, `WorkspaceSettings`, `CaseSettings`, `AgentContextSettings`, `AgentKnowledgeSettings`, `KnowledgeSkillSettings`, `PrePlanKnowledgeSettings`, `SkillConfig`, `OutputSettings`, `LocalToolOutputSettings`, and `ConfigurationError`.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `Settings`: Runtime settings aggregate model that combines agent runtime defaults, OpenAI Agents SDK provider selection, tracing policy, resolved provider runtime values, configurable prompt template paths and scalar variables, context trimming defaults, AgentTool output artifact policy defaults, Android/Web harness and driver selection, runner-owned post-action delay defaults, env-backed Android app/device settings, Web Playwright settings, strict-core platform readiness inputs, runtime secret allowlists for inherited CommonTools, workspace, case directory, output, and structured agent context rooted in a knowledge directory containing skill resources and optional pre-plan page knowledge.
- `load_settings(path: str | Path | None = None, workspace: str | Path | None = None) -> Settings`: Loads `.env` values without overriding existing environment variables, loads YAML configuration from the provided path or default search locations, overlays fixed environment-backed local settings, normalizes provider settings, and resolves runtime paths. The optional workspace argument overrides `workspace.root_dir`.
- `resolve_runtime_paths(settings: Settings, base_dir: Path | None = None) -> None`: Ensures the fsq-agent workspace is initialized and marked, resolves case directories, agent context knowledge root, knowledge-root-relative skills directory, optional pre-plan knowledge directory, optional prompt template paths, and creates output directories under the workspace.
- `validate_runtime_settings(settings: Settings) -> None`: Validates provider-specific environment/auth requirements, Azure OpenAI base URL shape when selected, resolved model name, LLM harness/driver/platform tool settings, AgentTool policy, platform CommonTool policy, and local path constraints before a default LLM run starts.
- `validate_strict_core_settings(settings: Settings, requires_ai_assertion: bool = False) -> None`: Validates strict-core harness/driver settings not provided by a case file. It does not require provider credentials unless the caller knows the strict run contains an authored `assertWithAI` step or otherwise requires a provider-backed AI assertion evaluator. Strict replay runtime-secret refs are validated by entry-layer code after the case is parsed because the referenced names come from the case, not from static settings.

Developer-owned YAML shape for execution post-action delay defaults and agent context must include this structure:

```yaml
harness:
	platform: android
	android:
		backend: uiautomator2

execution:
	post_action_delay_seconds:
		platform: 1.0
		common: 0.0

agent_context:
	knowledge:
		root_dir: ./knowledge
		skills:
			dir: skills
			items:
				- name: automation-basics
					description: Semantic action and evidence guidance for local runs.
					kind: markdown
					path: automation-basics.md
					required: true
		pre_plan:
			dir: project_android_v1
```

Web runs use the same shape with `harness.platform: web` and a nested Web settings object:

```yaml
harness:
	platform: web
	web:
		backend: playwright
		channel: chrome
		headless: false
		base_url: null
```

## Platform Configuration Blocks

Shared configuration rules:

- `harness.platform` selects the active platform for dynamic, strict, and playground entry surfaces.
- Platform-specific settings live under `harness.<platform>`.
- Validation must reject unsupported platform/backend combinations before external actions begin.

Android configuration:

- `harness.android.backend` supports `uiautomator2` in the first Android backend.
- `FSQ_ANDROID_APP_ID` and `FSQ_ANDROID_SERIAL` remain environment-backed local settings.
- Strict Android runs may fall back to FSQ case `appId` metadata where the CLI/playground strict entry permits it.

Web configuration:

- `harness.web.backend` supports `playwright` in the first Web backend.
- `harness.web.channel` selects the local browser channel. The first supported channel is `chrome`.
- `FSQ_WEB_BROWSER_EXECUTABLE_PATH` is a required environment-backed local Web setting. It must point to an existing browser executable file matching the configured channel, for example `chrome.exe` for `channel: chrome`.
- `harness.web.headless`, optional `harness.web.base_url`, and optional viewport fields are YAML-owned runtime shape.
- Missing Playwright packages are reported during Web runtime construction with actionable setup guidance, not during registry bootstrap. Missing, nonexistent, non-file, non-executable, or channel-mismatched Web browser executable paths are reported by configuration validation before external actions begin.

Future platform configuration:

- New platforms must add a nested settings model and validation block before implementation.
- New platform settings must not be hidden in unrelated Android/Web fields.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML loading, environment variable handling, fixed env overlay, default path discovery, provider-specific endpoint normalization, and runtime validation.
- `_settings.py`: `Settings` aggregate model.
- `_paths.py`: Workspace marker validation and runtime path resolution helpers.
- `SPEC.md`: Module design.

## Error Handling

Invalid or missing configuration raises `ConfigurationError` from `models`. Low-level YAML, path, workspace marker, environment overlay, or validation exceptions are wrapped with actionable context. Missing Azure OpenAI, Android local environment values, or Web browser executable path values are reported by variable name without exposing secret values. Web settings validation reports unsupported backend/channel/headless/base URL values and invalid browser executable paths without launching Playwright. Negative post-action delay defaults are rejected. Obsolete `harness.strict_core.step_interval_seconds` configuration is rejected instead of silently preserving strict-only pacing; users should configure `execution.post_action_delay_seconds` instead. Obsolete `verification` configuration, including `verification.mode`, is rejected instead of ignored. Obsolete custom instruction configuration under `openai_agents.prompt.custom_instructions` or `openai_agents.prompt.custom_instructions_path` is rejected instead of ignored; users should move that guidance into `knowledge/project.md` or configured skills. Removed pre-release config keys do not require custom migration errors; they are rejected by the narrowed settings schema when present.

## Design Decisions

- Configuration is read once during application startup and passed into modules explicitly.
- Runtime configuration has two ownership layers: `.env` and process environment hold local user values that vary by machine, account, device, or cloud deployment; YAML holds developer-owned runtime shape and safety policy. Process environment variables take precedence over `.env` values.
- The default provider is `github_copilot`. GitHub Copilot uses runtime device-code authentication on first run, caches the GitHub OAuth token under `workspace.root_dir/auth/github-copilot-token.json`, and uses Copilot model `gpt-5.5`. No GitHub token value, Copilot token value, or Copilot model override is configured in YAML.
- Azure OpenAI remains available only when YAML explicitly sets `openai_agents.provider: azure_openai`. Azure provider configuration is read from fixed environment variable names: `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY`. Azure endpoint values are normalized to the OpenAI-compatible Responses base URL form, for example `https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/`. GitHub Copilot mode ignores Azure environment variables.
- API keys and test credentials are never stored in config YAML. Runtime-only secret values come from process environment or `.env`; the `runtime_secrets.allowed_env_names` YAML allowlist remains the developer-owned policy naming which environment variables `get_runtime_secret` may return to the model and which recorded strict cases may reference through `runtimeSecret` refs.
- Android app and device values are local user settings. `FSQ_ANDROID_APP_ID` supplies the Android application id for dynamic LLM runs and strict-core runs that do not provide `appId` in FSQ case metadata. `FSQ_ANDROID_SERIAL` optionally selects the Android device serial passed to the uiautomator2 backend; an empty value means no serial override.
- `openai_agents.provider` selects the shared model provider. Provider construction and token exchange are implemented by `providers`, not by `config`.
- Tracing is enabled by default through `openai_agents.tracing_enabled: true`, and the CLI may override that setting for one run. The runtime enables OpenAI Agents SDK trace export only when `OPENAI_API_KEY` is present for the SDK exporter; otherwise it disables SDK tracing for the run so GitHub Copilot and Azure OpenAI executions do not repeatedly log missing OpenAI trace-export-key warnings. Sensitive tracing is fixed off; `trace_include_sensitive_data` is not a YAML or CLI option.
- Context trimming and AgentTool local output artifact policy are internal defaults, not part of the default YAML surface. The defaults keep recent moderate AgentTool and platform capability outputs inline, write complete large helper outputs to per-run artifacts, and trim older large SDK tool outputs before model calls.
- `shell`, `cli_tools`, YAML provider endpoint/key/model fields, YAML Android app id/serial fields, sensitive tracing, workspace marker/autoinit settings, and one-option output policy switches are removed from the external YAML config surface.
- fsq-agent never writes runtime artifacts relative to the caller's current directory. A configured workspace resolves from `--workspace` or `workspace.root_dir`; when neither is set, the default workspace is the `.fsq-agent-workspace` directory next to the resolved config file, or under the current directory only when no config file is discovered. Every workspace is initialized with the `.fsq-agent-workspace` marker file; non-empty unmarked directories are rejected to avoid treating a public user directory as a managed workspace.
- Relative `cases.dir` and `agent_context.knowledge.root_dir` values resolve relative to the configuration file directory. Relative `agent_context.knowledge.skills.dir` and `agent_context.knowledge.pre_plan.dir` values resolve under the resolved knowledge root. Relative `output.root_dir` values resolve inside the fsq-agent workspace.
- `agent_context.knowledge.root_dir` is the normal task private knowledge root. `agent_context.knowledge.skills.dir` defaults to `skills`, so configured skill item paths resolve under the existing `knowledge/skills` layout. `agent_context.knowledge.skills.items` is the configured automation skill list. `agent_context.knowledge.pre_plan.dir` optionally points internal dynamic goal planning at a reusable page-knowledge graph under the same knowledge root; when omitted, internal planning falls back to the knowledge root.
- `openai_agents.prompt` owns prompt template customization and scalar prompt variables. `prompt.agent_template_path` and `prompt.task_template_path` may point to files resolved relative to the configuration file directory; when template paths are omitted, package default templates are used. Static prompt text, headings, loops, and task formatting live in templates. `prompt.variables` provides operator-controlled scalar model data injected into templates. `prompt.custom_instructions` and `prompt.custom_instructions_path` are not supported configuration keys; project-specific guidance belongs in `knowledge/project.md`, and reusable execution guidance belongs in configured skills.
- `harness.platform` selects the platform harness used by goal-driven task execution and strict-core execution. Supported platforms are `android` and `web`.
- `harness.android.backend` selects the Android backend. The first supported backend is `uiautomator2`.
- `harness.web.backend` selects the Web backend. The first supported backend is `playwright`. `harness.web.channel` selects the local Playwright browser channel, with `chrome` supported to use the locally installed Google Chrome executable configured by `FSQ_WEB_BROWSER_EXECUTABLE_PATH`; `harness.web.headless` controls local browser visibility; `harness.web.base_url` is optional YAML-owned developer configuration used by entry layers when strict Web cases author relative navigation URLs. The first Web batch does not read Web base URL from a fixed environment variable.
- `execution.post_action_delay_seconds` controls runner-owned post-action stabilization delay defaults. `platform` defaults to `1.0` seconds and applies to PlatformTool capabilities when capability metadata does not override it. `common` defaults to `0.0` seconds and applies to inherited CommonTool capabilities when capability metadata does not override it. Values must be non-negative, and this pacing is execution timing only: it must not add `waitMs` commands, mutate parsed FSQ commands, record generated strict replay waits, or create synthetic evidence steps.
- Android app id and device serial are environment-backed local values, not YAML values. Strict-core may fall back to `appId` from parsed FSQ case metadata when `FSQ_ANDROID_APP_ID` is absent. There are no public CLI app-id overrides. Web strict-core does not require Android app id or device serial.
- Playwright package installation is operator-managed through the `web` extra. Browser channel selection is YAML-owned through `harness.web.channel`; browser executable selection is local-user-owned through `FSQ_WEB_BROWSER_EXECUTABLE_PATH`. Configuration validation checks the env var is configured, exists, points to a file, is executable on POSIX hosts, and matches the configured channel before external actions begin.
- Strict-core execution remains deterministic except for explicitly authored `assertWithAI` assertion steps. When a strict run contains `assertWithAI`, entry-layer code may request provider validation and inject a provider-backed evaluator into the active harness/backend support. Missing provider readiness for such a step is a configuration failure. No AI recovery, locator fallback, or testcase mutation is enabled by this setting.
- Strict replay secret refs remain deterministic configuration inputs. After parsing a strict case, entry-layer code validates each referenced `runtimeSecret` name against `runtime_secrets.allowed_env_names` and verifies the value is present in environment or `.env` before UI actions begin. Missing allowlist entries or values are configuration failures. Secret values are substituted only in memory and must not be written to settings, generated YAML, events, manifests, or reports.
- Dynamic LLM final verification is not configurable through settings. The runtime verifies the single pre-plan-derived `verification_goal`; `verification.mode` is obsolete and must not be accepted.
- Non-interactive execution is the default. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Output directory creation is part of config resolution so later modules can assume directories are writable. Reports, run event timelines, AgentTool artifacts, platform evidence artifacts, and generated files must be placed under `output.root_dir`; completed run reports are stored under `output.runs_dir`.
- Platform action schemas are not configured through external tool servers. They are declared by decorated capability hosts, validated in the capability registry, and adapted by the agent runtime into SDK `FunctionTool` objects.
- Top-level `skills`, top-level `knowledge_dir`, and top-level `pre_plan` YAML keys are removed from the external config surface. Agent context must be expressed through `agent_context.knowledge` so the relationship between the knowledge root, skill files, and pre-plan page knowledge remains explicit.