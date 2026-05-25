# fsq-agent

fsq-agent is a goal-driven automated testing agent for FSQ YAML-guided tasks. It uses OpenAI Agents SDK with Azure OpenAI, executes MCP or CLI capabilities, captures evidence, verifies acceptance criteria, and generates reports.

The project follows spec-driven development. See [CLAUDE.md](CLAUDE.md) and each module `SPEC.md` before changing public interfaces.

See [docs/openai-agent-loop.md](docs/openai-agent-loop.md) for how task execution loops through OpenAI Agents SDK, MCP tools, verification, and reporting.

## Quick Start

```bash
python -m pip install -e ".[dev]"
copy .env.example .env
fsq-agent init --config config.example.yaml
fsq-agent capabilities --config config.example.yaml
fsq-agent validate-config --config config.example.yaml
fsq-agent run --config config.example.yaml --task examples/tasks/add-bookmark.codex.yaml
fsq-agent run-goal --config config.example.yaml --goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
```

Set `AZURE_OPENAI_API_KEY` in `.env` before enabling the OpenAI Agents SDK runtime. The Azure OpenAI base URL should use the `/openai/v1/` form and the model value is the deployment name, for example `gpt-5.4`. Existing process environment variables take precedence over `.env` values.

Final verification strictness is configured with `verification.mode`. The default `normal` verifies the case goal and assertion key actions, `strict` verifies the goal plus every key action including operations, and `goal` verifies only the case goal. Execution still receives the full key-action flow in every mode.

## Goal-Driven Tasks

Use `run-goal` when you want the agent to start from a natural-language goal instead of an FSQ case with explicit key actions:

```bash
fsq-agent run-goal \
	--config config.local.yaml \
	--goal "Access Downloads through the browser overflow menu from the New Tab Page, then return to the New Tab Page."
```

`run-goal` first runs the same goal pre-planner used by `pre-plan`, injects the generated key actions into the normal execution flow, then runs verification and report generation as one task run. The pre-plan phase is recorded in the task run timeline; it does not create a separate report.

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
fsq-agent run --config config.local.yaml --task path/to/goal-only.codex.yaml
```

Use `pre-plan` when you only want to inspect the generated key actions without executing UI automation, verification, or report generation:

```bash
fsq-agent pre-plan --config config.local.yaml --goal "Open Downloads from the New Tab Page" --format json
```

## Current Scope

This implementation provides validated models, configuration loading, OpenAI Agents SDK runtime wiring, MCP configuration, allowlisted CLI execution, optional SDK ShellTool execution, descriptive skill loading, evidence manifests, and report generation. Task execution requires the OpenAI Agents SDK package and authentication for the selected `openai_agents.provider`.

Local shell execution is disabled by default. Enable `shell.enabled` with `shell.mode: allowlist` for normal command restrictions, or `shell.mode: allow_all` for intentionally unrestricted local runs inside the fsq-agent workspace. Runtime artifacts are written under the configured workspace `output` directory.