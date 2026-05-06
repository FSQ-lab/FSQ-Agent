# Auto Test Agent

Auto Test Agent is a goal-driven automated testing agent for natural-language tasks. It uses OpenAI Agents SDK with Azure OpenAI, executes MCP or CLI capabilities, captures evidence, verifies acceptance criteria, and generates reports.

The project follows spec-driven development. See [CLAUDE.md](CLAUDE.md) and each module `SPEC.md` before changing public interfaces.

See [docs/openai-agent-loop.md](docs/openai-agent-loop.md) for how task execution loops through OpenAI Agents SDK, MCP tools, verification, and reporting.

## Quick Start

```bash
python -m pip install -e ".[dev]"
copy .env.example .env
auto-test-agent capabilities --config config.example.yaml
auto-test-agent validate-config --config config.example.yaml
auto-test-agent run --config config.example.yaml --task examples/tasks/add-bookmark.yaml
```

Set `AZURE_OPENAI_API_KEY` in `.env` before enabling the OpenAI Agents SDK runtime. The Azure OpenAI base URL should use the `/openai/v1/` form and the model value is the deployment name, for example `gpt-5.4`. Existing process environment variables take precedence over `.env` values.

## Current Scope

This implementation provides validated models, configuration loading, OpenAI Agents SDK runtime wiring, MCP configuration, allowlisted CLI execution, optional SDK ShellTool execution, descriptive skill loading, evidence manifests, and report generation. Task execution requires OpenAI Agents SDK to be enabled and `AZURE_OPENAI_API_KEY` to be present.

Local shell execution is disabled by default. Enable `shell.enabled` with `shell.mode: allowlist` for normal command restrictions, or `shell.mode: allow_all` for intentionally unrestricted local runs.