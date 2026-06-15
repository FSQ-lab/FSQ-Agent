# Config And Env Simplification Design

## Goal

Simplify fsq-agent runtime configuration so the default path is easy to run locally with GitHub Copilot, while Azure OpenAI remains available as an explicit developer-selected provider. Align `.env` with `.env.example` and `config.local.yaml` with `config.example.yaml`, remove stale or unused configuration, and keep user-specific local values out of YAML.

## Scope

This design covers the external runtime configuration surface owned by `fsq_agent.config` and the code paths that consume those settings in CLI, provider construction, Android harness construction, and documentation.

In scope:

- Default provider behavior and sample configuration.
- `.env` / `.env.example` keys for local user values.
- `config.local.yaml` / `config.example.yaml` shape for developer-owned runtime policy.
- CLI tracing override behavior.
- Removal of unused, stale, or overly broad YAML configuration fields.
- Tests and documentation needed to verify the new behavior.

## Non-Goals

- Do not remove Azure OpenAI support. It remains available when a developer explicitly selects `provider: azure_openai`.
- Do not move runtime secret allowlisting entirely into `.env`. Secret values belong in `.env`, but the allowlist of names the model may read remains a developer-owned safety policy in YAML.
- Do not redesign CommonTool, strict replay, Android driver actions, or provider internals beyond the configuration inputs they consume.
- Do not persist or document local secret values from `.env`.
- Do not add bespoke deprecated-key migration checks. This project is still in active debugging and has not published a stable config contract; removed schema keys can simply stop being accepted.

## Proposed Design

### Configuration Ownership

Use two configuration layers:

- `.env` / `.env.example` hold local user values that differ by machine, account, device, or cloud deployment.
- `config.local.yaml` / `config.example.yaml` hold developer-owned runtime shape and safety policy.

Process environment variables continue to take precedence over `.env` values. `.env` values must not override already-set process environment variables.

### Default `.env.example` Shape

The default `.env.example` should use the same key set expected in local `.env`:

```dotenv
# Android local device/app settings.
FSQ_ANDROID_APP_ID=com.microsoft.emmx
FSQ_ANDROID_SERIAL=

# Account-dependent tasks. Values stay local and are only readable when config allowlists the names.
TEST_ACCOUNT_EMAIL=
TEST_ACCOUNT_PASSWORD=

# Azure OpenAI only when config selects provider: azure_openai.
AZURE_OPENAI_BASE_URL=
AZURE_OPENAI_MODEL=
AZURE_OPENAI_API_KEY=
```

`FSQ_ANDROID_SERIAL` treats an empty value as no serial override. Local `.env` may contain secret values, but those values must never be copied into examples, docs, reports, events, generated YAML, or final responses.

### Default YAML Shape

The default `config.example.yaml` and `config.local.yaml` should share the same schema and minimal shape:

```yaml
openai_agents:
  provider: github_copilot
  tracing_enabled: true

harness:
  platform: android
  android:
    backend: uiautomator2

runtime_secrets:
  allowed_env_names:
    - TEST_ACCOUNT_EMAIL
    - TEST_ACCOUNT_PASSWORD

skills:
  - name: automation-basics
    description: Semantic action and evidence guidance for local runs.
    kind: markdown
    path: automation-basics.md
    required: true
  - name: android-harness
    description: Android harness action selection and recovery guidance.
    kind: markdown
    path: android-harness.md
    required: true

knowledge_dir: ./knowledge

pre_plan:
  knowledge_dir: ./knowledge/project_android_v1
```

GitHub Copilot is the default provider. The runtime uses Copilot model `gpt-5.5` for `github_copilot`; no YAML model override is part of the default configuration surface.

Azure OpenAI remains developer-selected by setting:

```yaml
openai_agents:
  provider: azure_openai
  tracing_enabled: true
```

When `azure_openai` is selected, the loader reads Azure values from environment:

- `AZURE_OPENAI_BASE_URL`
- `AZURE_OPENAI_MODEL`
- `AZURE_OPENAI_API_KEY`

Azure endpoint normalization to `/openai/v1/` remains part of settings normalization. GitHub Copilot mode ignores Azure environment variables.

### Retained YAML Fields

The default YAML should be small, but these developer-owned fields remain part of the configuration contract unless a later SPEC update removes them explicitly:

- `openai_agents.provider`
- `openai_agents.tracing_enabled`
- `harness.platform`
- `harness.android.backend`
- `runtime_secrets.allowed_env_names`
- `skills`
- `knowledge_dir`
- `pre_plan.knowledge_dir`

Advanced developer fields may remain supported when they are actively consumed and are not one-option switches, but they should not appear in the default examples. Current candidates are `openai_agents.max_turns`, `openai_agents.prompt`, `agent.step_timeout_seconds`, `workspace.root_dir`, `cases.dir`, and `output.root_dir`. The SPEC update should keep only fields with a concrete runtime consumer and a clear developer ownership story.

### Removed Or Internalized YAML Fields

The following fields should be removed from the external YAML config surface or kept only as internal code defaults:

- `openai_agents.base_url`, `openai_agents.api_key_env`, and `openai_agents.model`: Azure values move to fixed env names; Copilot uses its default model.
- `openai_agents.fail_without_api_key`: fixed true.
- `openai_agents.trace_include_sensitive_data`: fixed false.
- `openai_agents.context_trimming` and `openai_agents.local_tool_output`: internal defaults, not default YAML knobs.
- `agent.model`, `agent.max_steps`, and `agent.max_retries`: not part of the active runtime path and should be removed from public config.
- `harness.android.app_id` and `harness.android.serial`: move to `FSQ_ANDROID_APP_ID` and `FSQ_ANDROID_SERIAL`.
- `shell` and `cli_tools`: removed because local CLI/shell execution is not part of the public CommonTool contract.
- `workspace.marker_file` and `workspace.auto_init`: fixed internal workspace policy.
- One-option fields such as `local_tool_output.historical_output_mode`: fixed internally instead of configurable.

The implementation does not need hand-written deprecated-key checks. Removing the schema fields is enough for this pre-release configuration surface.

### CLI Tracing Override

Tracing defaults to enabled:

- `OpenAIAgentsSettings.tracing_enabled` default becomes `true`.
- `config.example.yaml` and `config.local.yaml` show `tracing_enabled: true`.
- `fsq-agent run` adds `--tracing / --no-tracing`.
- CLI tracing override is applied after settings load and before runtime validation or dynamic execution.
- When neither CLI flag is supplied, config/default behavior applies.
- Sensitive tracing remains disabled; no CLI or YAML option enables `trace_include_sensitive_data`.

### Loading Flow

The expected flow is:

1. Load `.env` files from the repository/config locations without overriding process env.
2. Read YAML settings with the narrowed schema.
3. Overlay local env values into settings for Android app id and serial.
4. Normalize provider settings:
   - `github_copilot`: provider default model is `gpt-5.5`; Azure env is not required.
   - `azure_openai`: require Azure base URL, model, and API key from env; normalize base URL to `/openai/v1/`.
5. Resolve paths as part of settings loading.
6. Apply CLI tracing override when provided, after `load_settings` returns and before validating or executing the requested mode.

Missing required Azure env values or Android app id values should produce `ConfigurationError` messages that identify the missing variable names or config/case alternatives, without exposing secret values.

## Affected Specs Expected To Change

The next `spec-driven` step should update:

- Root `SPEC.md`: likely no module table change, but confirm the config/provider behavior remains accurately summarized.
- `fsq_agent/config/SPEC.md`: update default provider, env overlay behavior, simplified YAML schema, tracing CLI override expectations, and removed config fields.
- `fsq_agent/models/SPEC.md`: update `OpenAIAgentsSettings`, Android harness settings, runtime secret settings, and any removed or internal-only setting models.
- `fsq_agent/providers/SPEC.md`: update Azure provider config source from YAML fields to fixed environment variable names while keeping Copilot behavior.
- `fsq_agent/cli/SPEC.md`: add `run --tracing / --no-tracing` behavior and describe when CLI overrides apply.
- `fsq_agent/tools/SPEC.md`: no behavioral change expected, but verify `shell` and `cli_tools` remain absent from the public tool contract.
- README and sample files: update quick start and runtime configuration docs to match the new default Copilot path and env/config split.

## Open Questions Resolved During Discussion

- Azure OpenAI remains supported as a developer-selected provider, not the default path.
- The chosen approach is strict configuration surface convergence, not sample-only cleanup and not broad backward compatibility.
- `harness.platform` and `harness.android.backend` remain in YAML even though the current implementation has one supported platform/backend.
- Tracing defaults to enabled and can be overridden from CLI with `--tracing / --no-tracing`.
- No dedicated deprecated-key checks are needed because the project is still in active debugging and has not published the old config surface.
- Runtime secret values belong in `.env`; `runtime_secrets.allowed_env_names` remains in YAML as the developer-owned safety policy.

## Verification Expectations

After SPEC updates and implementation, verification should cover:

- `config.example.yaml` and `config.local.yaml` use the same default schema keys.
- `.env.example` and local `.env` use the same expected key names, with local values preserved and never printed.
- `load_settings` defaults to `github_copilot`, `gpt-5.5`, and `tracing_enabled=true` when no explicit provider/model/tracing override is present.
- `FSQ_ANDROID_APP_ID` and `FSQ_ANDROID_SERIAL` populate Android runtime settings, with blank serial treated as `None`.
- `azure_openai` reads `AZURE_OPENAI_BASE_URL`, `AZURE_OPENAI_MODEL`, and `AZURE_OPENAI_API_KEY` from environment and preserves endpoint normalization.
- `github_copilot` does not require Azure env values.
- `fsq-agent run --tracing` and `fsq-agent run --no-tracing` override config/default tracing behavior.
- Removed YAML fields such as `shell`, `cli_tools`, YAML Azure endpoint/key/model fields, YAML Android app id/serial fields, and sensitive tracing options are no longer part of the Settings schema.
- README quick start uses the Copilot default path and documents Azure as an explicit developer option.
- The final implementation receives an independent diff-based SPEC implementation audit before completion is claimed.