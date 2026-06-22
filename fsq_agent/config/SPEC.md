# Module: config

## Purpose

Load, merge, normalize, and validate runtime configuration for the OpenAI Agents SDK runtime, shared model provider selection, env-backed Azure OpenAI settings, GitHub Copilot local provider authentication, env-backed Android app/device selection, harness/driver construction, harness-owned strict-core pacing, strict-core Android readiness, strict replay secret resolution, CommonTool safety policy, agent-context knowledge and skills, runtime secret allowlists, case input directories, internal goal-planning page knowledge, the fsq-agent workspace, and output directories.

## Dependencies

- `models`: Uses `AgentSettings`, `OpenAIAgentsSettings`, `RuntimeSecretSettings`, `HarnessSettings`, `AndroidHarnessSettings`, `StrictCoreHarnessSettings`, `WorkspaceSettings`, `CaseSettings`, `AgentContextSettings`, `AgentKnowledgeSettings`, `KnowledgeSkillSettings`, `PrePlanKnowledgeSettings`, `SkillConfig`, `OutputSettings`, `LocalToolOutputSettings`, and `ConfigurationError`.

## Public Interface

Target `__init__.py` exports via `__all__` after this change:

- `Settings`: Runtime settings aggregate model that combines agent runtime defaults, OpenAI Agents SDK provider selection, tracing policy, resolved provider runtime values, configurable prompt text, context trimming defaults, CommonTool output artifact policy defaults, harness/driver selection, harness strict-core pacing, env-backed Android app/device settings, strict-core Android readiness inputs, runtime secret allowlists, workspace, case directory, output, and structured agent context rooted in a knowledge directory containing skill resources and optional pre-plan page knowledge.
- `load_settings(path: str | Path | None = None, workspace: str | Path | None = None) -> Settings`: Loads `.env` values without overriding existing environment variables, loads YAML configuration from the provided path or default search locations, overlays fixed environment-backed local settings, normalizes provider settings, and resolves runtime paths. The optional workspace argument overrides `workspace.root_dir`.
- `resolve_runtime_paths(settings: Settings, base_dir: Path | None = None) -> None`: Ensures the fsq-agent workspace is initialized and marked, resolves case directories, agent context knowledge root, knowledge-root-relative skills directory, optional pre-plan knowledge directory, and creates output directories under the workspace.
- `validate_runtime_settings(settings: Settings) -> None`: Validates provider-specific environment/auth requirements, Azure OpenAI base URL shape when selected, resolved model name, LLM harness/driver settings, CommonTool policy, and local path constraints before a default LLM run starts.
- `validate_strict_core_settings(settings: Settings, requires_ai_assertion: bool = False) -> None`: Validates strict-core harness/driver settings not provided by a case file. It does not require provider credentials unless the caller knows the strict run contains an authored `assertWithAI` step or otherwise requires a provider-backed AI assertion evaluator. Strict replay runtime-secret refs are validated by entry-layer code after the case is parsed because the referenced names come from the case, not from static settings.

Developer-owned YAML shape for harness strict-core pacing and agent context must include this structure:

```yaml
harness:
	platform: android
	android:
		backend: uiautomator2
	strict_core:
		step_interval_seconds: 1.0

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

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: YAML loading, environment variable handling, fixed env overlay, default path discovery, provider-specific endpoint normalization, and runtime validation.
- `_settings.py`: `Settings` aggregate model.
- `_paths.py`: Workspace marker validation and runtime path resolution helpers.
- `SPEC.md`: Module design.

## Error Handling

Invalid or missing configuration raises `ConfigurationError` from `models`. Low-level YAML, path, workspace marker, environment overlay, or validation exceptions are wrapped with actionable context. Missing Azure OpenAI or Android local environment values are reported by variable name without exposing values. Obsolete `verification` configuration, including `verification.mode`, is rejected instead of ignored. Removed pre-release config keys do not require custom migration errors; they are rejected by the narrowed settings schema when present.

## Design Decisions

- Configuration is read once during application startup and passed into modules explicitly.
- Runtime configuration has two ownership layers: `.env` and process environment hold local user values that vary by machine, account, device, or cloud deployment; YAML holds developer-owned runtime shape and safety policy. Process environment variables take precedence over `.env` values.
- The default provider is `github_copilot`. GitHub Copilot uses runtime device-code authentication on first run, caches the GitHub OAuth token under `workspace.root_dir/auth/github-copilot-token.json`, and uses Copilot model `gpt-5.5`. No GitHub token value, Copilot token value, or Copilot model override is configured in YAML.
- Azure OpenAI remains available only when YAML explicitly sets `openai_agents.provider: azure_openai`. Azure provider configuration is read from fixed environment variable names: `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY`. Azure endpoint values are normalized to the OpenAI-compatible Responses base URL form, for example `https://edgeqa-resource.cognitiveservices.azure.com/openai/v1/`. GitHub Copilot mode ignores Azure environment variables.
- API keys and test credentials are never stored in config YAML. Runtime-only secret values come from process environment or `.env`; the `runtime_secrets.allowed_env_names` YAML allowlist remains the developer-owned policy naming which environment variables `get_runtime_secret` may return to the model and which recorded strict cases may reference through `runtimeSecret` refs.
- Android app and device values are local user settings. `FSQ_ANDROID_APP_ID` supplies the Android application id for dynamic LLM runs and strict-core runs that do not provide `appId` in FSQ case metadata. `FSQ_ANDROID_SERIAL` optionally selects the Android device serial passed to the uiautomator2 backend; an empty value means no serial override.
- `openai_agents.provider` selects the shared model provider. Provider construction and token exchange are implemented by `providers`, not by `config`.
- Tracing is enabled by default through `openai_agents.tracing_enabled: true`, and the CLI may override that setting for one run. The runtime enables OpenAI Agents SDK trace export only when `OPENAI_API_KEY` is present for the SDK exporter; otherwise it disables SDK tracing for the run so GitHub Copilot and Azure OpenAI executions do not repeatedly log missing OpenAI trace-export-key warnings. Sensitive tracing is fixed off; `trace_include_sensitive_data` is not a YAML or CLI option.
- Context trimming and CommonTool local output artifact policy are internal defaults, not part of the default YAML surface. The defaults keep recent moderate CommonTool and harness outputs inline, write complete CommonTool outputs to per-run artifacts, and trim older large SDK tool outputs before model calls.
- `shell`, `cli_tools`, YAML provider endpoint/key/model fields, YAML Android app id/serial fields, sensitive tracing, workspace marker/autoinit settings, and one-option output policy switches are removed from the external YAML config surface.
- fsq-agent never writes runtime artifacts relative to the caller's current directory. A configured workspace resolves from `--workspace` or `workspace.root_dir`; when neither is set, the default workspace is the `.fsq-agent-workspace` directory next to the resolved config file, or under the current directory only when no config file is discovered. Every workspace is initialized with the `.fsq-agent-workspace` marker file; non-empty unmarked directories are rejected to avoid treating a public user directory as a managed workspace.
- Relative `cases.dir` and `agent_context.knowledge.root_dir` values resolve relative to the configuration file directory. Relative `agent_context.knowledge.skills.dir` and `agent_context.knowledge.pre_plan.dir` values resolve under the resolved knowledge root. Relative `output.root_dir` values resolve inside the fsq-agent workspace.
- `agent_context.knowledge.root_dir` is the normal task private knowledge root. `agent_context.knowledge.skills.dir` defaults to `skills`, so configured skill item paths resolve under the existing `knowledge/skills` layout. `agent_context.knowledge.skills.items` is the configured automation skill list. `agent_context.knowledge.pre_plan.dir` optionally points internal dynamic goal planning at a reusable page-knowledge graph under the same knowledge root; when omitted, internal planning falls back to the knowledge root.
- `openai_agents.prompt` owns prompt customization. `prompt.agent_template_path`, `prompt.task_template_path`, and `prompt.custom_instructions_path` may point to files resolved relative to the configuration file directory; when template paths are omitted, package default templates are used. Static prompt text, headings, loops, and task formatting live in templates. Long operator guidance should live in `prompt.custom_instructions_path`; `prompt.custom_instructions` remains available for short inline overrides, and `prompt.variables` provides operator-controlled scalar model data injected into templates.
- `harness.platform` selects the platform harness used by goal-driven task execution. The first supported platform is `android`.
- `harness.android.backend` selects the Android backend. The first supported backend is `uiautomator2`.
- `harness.strict_core.step_interval_seconds` controls the interval passed from entry-layer strict execution into `StepSequenceRunner`. The default is `1.0` seconds, values must be non-negative, and this pacing is execution timing only: it must not add `waitMs` commands, mutate parsed FSQ commands, or create synthetic evidence steps.
- Android app id and device serial are environment-backed local values, not YAML values. Strict-core may fall back to `appId` from parsed FSQ case metadata when `FSQ_ANDROID_APP_ID` is absent. There are no public CLI app-id overrides.
- Strict-core execution remains deterministic except for explicitly authored `assertWithAI` assertion steps. When a strict run contains `assertWithAI`, entry-layer code may request provider validation and inject a provider-backed evaluator into the platform harness. Missing provider readiness for such a step is a configuration failure. No AI recovery, locator fallback, or testcase mutation is enabled by this setting.
- Strict replay secret refs remain deterministic configuration inputs. After parsing a strict case, entry-layer code validates each referenced `runtimeSecret` name against `runtime_secrets.allowed_env_names` and verifies the value is present in environment or `.env` before UI actions begin. Missing allowlist entries or values are configuration failures. Secret values are substituted only in memory and must not be written to settings, generated YAML, events, manifests, or reports.
- Dynamic LLM final verification is not configurable through settings. The runtime verifies the single pre-plan-derived `verification_goal`; `verification.mode` is obsolete and must not be accepted.
- Non-interactive execution is the default. Any human-in-the-loop SDK feature must be disabled or backed by deterministic programmatic approval.
- Output directory creation is part of config resolution so later modules can assume directories are writable. Reports, run event timelines, CommonTool artifacts, and generated files must be placed under `output.root_dir`; completed run reports are stored under `output.runs_dir`.
- Platform action schemas are not configured through external tool servers. They are discovered from the active harness through `HarnessInterface.action_space()` and adapted by the agent runtime into SDK `FunctionTool` objects.
- Top-level `skills`, top-level `knowledge_dir`, and top-level `pre_plan` YAML keys are removed from the external config surface. Agent context must be expressed through `agent_context.knowledge` so the relationship between the knowledge root, skill files, and pre-plan page knowledge remains explicit.