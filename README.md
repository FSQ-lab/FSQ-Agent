# fsq-agent

fsq-agent is a goal-driven automated testing agent for FSQ YAML-guided tasks. It uses OpenAI Agents SDK with Azure OpenAI or GitHub Copilot, executes harness-generated platform actions plus configured local utilities, captures evidence, verifies one pre-plan-derived goal, and generates reports.

The project follows spec-driven development. See root [SPEC.md](SPEC.md) and each relevant module `SPEC.md` before changing public interfaces.

See [docs/openai-agent-loop.md](docs/openai-agent-loop.md) for how task execution loops through OpenAI Agents SDK, harness tools, local utilities, verification, and reporting.

## Quick Start

```bash
python -m pip install -e ".[dev,android]"
copy .env.example .env
fsq-agent init --config config.example.yaml
fsq-agent run --config config.example.yaml --goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
fsq-agent run --config config.example.yaml --case-yaml cases/android/example.codex.yaml
fsq-agent run --config config.example.yaml --strict --case-yaml cases/android/example.codex.yaml
fsq-agent report --config config.example.yaml --run-id RUN_ID --format markdown
```

## Runtime Configuration

Choose one model provider in config before running a full task:

- `openai_agents.provider: azure_openai` requires `AZURE_OPENAI_API_KEY` in process env or `.env`. `base_url` must use the `/openai/v1/` form, and `model` is the Azure deployment name, for example `gpt-5.4`.
- `openai_agents.provider: github_copilot` does not use an API-key env var. On first run it prompts for GitHub device-code auth and caches the OAuth token under `workspace.root_dir/auth/github-copilot-token.json`; use `model: gpt-5.5`.

For Android runs, install the Android extra, connect an emulator/device, and set `harness.android` in config:

```yaml
harness:
	platform: android
	android:
		backend: uiautomator2
		app_id: com.microsoft.emmx
		serial: null
```

`app_id` is required for dynamic LLM runs and for strict cases that do not provide `appId` in FSQ case metadata. Set `serial` to an `adb devices` serial when more than one device is connected; otherwise leave it `null`.

For account-dependent cases, put secret values in `.env` and allow only those names in config:

```yaml
runtime_secrets:
	allowed_env_names:
		- TEST_ACCOUNT_EMAIL
		- TEST_ACCOUNT_PASSWORD
```

Existing process environment variables take precedence over `.env` values. Secret values must not be stored in config YAML.

Dynamic LLM runs do not expose a verification-mode setting. Before UI actions begin, pre-plan summarizes the input into ordered execution key actions plus one `verification_goal`; the final verifier checks that single goal against execution evidence. Existing configs that still contain `verification` or `verification.mode` fail validation so the obsolete setting is not silently ignored.

## Running Tasks

Use `run --goal` when you want the agent to start from a natural-language goal:

```bash
fsq-agent run \
	--config config.local.yaml \
	--goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
```

Use `run --case-yaml` or `run --case-dir` for dynamic LLM execution from FSQ YAML reference material. In this mode the CLI reads each `.codex.yaml` file as raw UTF-8 text; it does not parse YAML, extract key actions, derive final verifier requirements, or convert commands into local steps. YAML steps are advisory and may be inaccurate; pre-plan prefers case-level intent when summarizing the final `verification_goal`.

```bash
fsq-agent run --config config.local.yaml --case-yaml path/to/case.codex.yaml
fsq-agent run --config config.local.yaml --case-dir path/to/cases
```

Use `run --strict` for deterministic strict-core execution of authored FSQ YAML. This path parses `.codex.yaml`, runs it through the configured Android driver, writes `evidence-manifest.json`, and generates `core-report.md/json` without LLM participation.

```bash
fsq-agent run --config config.local.yaml --strict --case-yaml path/to/case.codex.yaml
fsq-agent run --config config.local.yaml --strict --case-dir path/to/cases
```

`init` initializes the workspace and reports readiness for both the default LLM run path and the strict-core path. Strict-only users do not need OpenAI credentials just to initialize or run `--strict` cases.

You can also create goal-only `.codex.yaml` cases by providing only case metadata. The case name is the goal, and key actions are derived at runtime:

```yaml
schemaVersion: fsq.ai-test/v1
name: Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page.
platform: android
appId: com.microsoft.emmx
tags:
	- goal-driven
```

Run it with the same command used for normal FSQ cases:

```bash
fsq-agent run --config config.local.yaml --case-yaml path/to/goal-only.codex.yaml
```

## Current Scope

This implementation provides validated models, configuration loading, OpenAI Agents SDK runtime wiring, harness/driver configuration, allowlisted CLI execution, optional SDK ShellTool execution, descriptive skill loading, evidence manifests, and report generation. Task execution requires the OpenAI Agents SDK package and authentication for the selected `openai_agents.provider`.

Local shell execution is disabled by default. Enable `shell.enabled` with `shell.mode: allowlist` for normal command restrictions, or `shell.mode: allow_all` for intentionally unrestricted local runs inside the fsq-agent workspace. Runtime artifacts are written under the configured workspace `output` directory.
