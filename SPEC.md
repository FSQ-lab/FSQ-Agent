# fsq-agent Project Specification

This repository uses spec-driven development. Root `SPEC.md` is the project-level specification and module navigation source of truth. Each module also owns a module-level `SPEC.md`.

## Spec-Driven Development Workflow

For non-trivial development:

1. Clarify requirements and produce a design document.
2. Update or create relevant module `SPEC.md` files from that design.
3. Get `SPEC.md` confirmation before implementation.
4. Implement only against confirmed `SPEC.md`.
5. If implementation reveals missing design, stop and update `SPEC.md` first.
6. Before claiming completion, run independent diff-based SPEC implementation audit.

Bug fixes that do not change public interfaces or intended behavior may skip the design document, but must still read relevant `SPEC.md` files and verify that the specs remain accurate.

## Recorded Strict Case Artifacts

Dynamic LLM runs may optionally record the actual successful replayable execution trace as a generated strict FSQ `.codex.yaml` artifact under the run output directory. Recording is a CLI-owned post-run behavior: the agent runtime persists events, while the CLI recorder converts replayable harness actions plus supported CommonTool dependencies into a strict candidate case. Generated cases must never mutate source cases or `cases.dir`, and runtime secret values must never be written to YAML, manifests, events, or reports.

Recorded strict cases may contain replay-only syntax such as `runtimeSecret` parameter references and `waitMs` pure-wait commands. Strict execution resolves `runtimeSecret` references in memory before UI actions begin and executes `waitMs` without platform driver side effects.

## Dynamic LLM Pre-Plan and Goal Verification

Dynamic LLM `--goal`, `--case-yaml`, and `--case-dir` runs use pre-plan as the input-understanding boundary before external UI actions begin. The pre-planner must produce structured ordered `key_actions` for the main execution loop and one `verification_goal` string for final evidence-based verification. Dynamic final verification is goal-only and has no user-configurable `verification.mode`.

Dynamic LLM `--case-yaml` and `--case-dir` runs read authored case files as raw UTF-8 reference text, not as strict executable steps. The CLI-owned dynamic task construction must preserve that full raw reference in explicit planning-reference fields. Raw YAML steps are advisory only for dynamic LLM execution: they may help infer an execution flow, but they are not assumed accurate and must not be transformed into local executable steps or final verifier requirements. For raw cases, pre-plan should prefer case-level intent signals such as name, metadata, tags, properties, and human-authored goal text when summarizing `verification_goal`; step content may provide supporting context when the case-level intent is incomplete or ambiguous. Dynamic recording continues to reconstruct replayable commands only from actual run events.

## Runtime Configuration Defaults

Default local LLM runs use GitHub Copilot provider authentication with Copilot model `gpt-5.5` and tracing enabled. Azure OpenAI remains available only when config explicitly selects `openai_agents.provider: azure_openai`; Azure endpoint, deployment/model, and API key values come from fixed environment variable names rather than YAML fields. Local user values such as Android app id, Android device serial, account secrets, and Azure provider values belong in process environment or `.env`. YAML config owns developer policy and runtime shape such as provider selection, tracing default, harness platform/backend, harness strict-core step interval, runtime secret allowlist, agent context knowledge-root resources, workspace root, cases root, and output root.

## Prompt Context Boundaries

Dynamic LLM prompt context has four distinct channels. `agent_instructions.j2` owns stable dynamic execution rules. `task_input.j2` owns one task's structured input, ordered key actions, and final `verification_goal`. `knowledge/project.md` owns tested-project-specific guidance loaded for normal dynamic execution. Configured skills under the knowledge root own composable execution guidance such as platform and harness rules. There is no separate custom-instruction configuration channel; ad hoc operator guidance must be represented as project knowledge or configured skills.

Loader diagnostics such as missing optional skills or missing optional knowledge references are operational signals and must not be rendered into model-facing prompts. Required skill failures remain fail-fast. Optional broken skills are skipped with operator-visible diagnostics and are not passed to the LLM as warning-only or partial guidance. Runtime Markdown knowledge and skill content should stay concise, current, and aligned with exposed harness/CommonTool capabilities.

## Module Table

| Module | SPEC | Purpose |
|---|---|---|
| models | fsq_agent/models/SPEC.md | Owns shared domain models, result types, replay reference models, and exceptions. |
| config | fsq_agent/config/SPEC.md | Loads and validates env/YAML runtime, provider, harness/driver, tracing, strict-core pacing, strict replay secret, agent context, common tool, and workspace configuration. |
| providers | fsq_agent/providers/SPEC.md | Builds shared Azure OpenAI and GitHub Copilot provider sessions for agent runs, verifier/pre-planner calls, and provider-backed AI assertion evaluators. |
| tools | fsq_agent/tools/SPEC.md | Provides SDK-neutral CommonTool capabilities, recordable wait/runtime-secret metadata, and the OpenAI Agents SDK adapter for file, artifact, wait, and allowlisted runtime-secret utilities. |
| observation | fsq_agent/observation/SPEC.md | Persists run event timelines; screenshots, UI trees, and other observations are represented by harness or CommonTool artifact refs. |
| knowledge | fsq_agent/knowledge/SPEC.md | Loads project-specific application knowledge and task-referenced knowledge assets. |
| fsq | fsq_agent/fsq/SPEC.md | Loads FSQ AI Test DSL YAML cases, validates replay references, and converts parsed cases into deterministic strict-core executable steps. |
| skills | fsq_agent/skills/SPEC.md | Loads complete configured automation skill instruction bundles and skips or fails broken bundles according to requiredness. |
| report | fsq_agent/report/SPEC.md | Generates LLM task reports, strict-core evidence reports, and resolves stored reports by run id. |
| core | fsq_agent/core/SPEC.md | Defines shared execution-core orchestration boundaries, StepRunner protocol, pure waits, harness interface, and evidence coordination. |
| agent | fsq_agent/agent/SPEC.md | Orchestrates dynamic goal/reference execution through OpenAI Agents SDK, verification, replayable event metadata, and report generation. |
| playground | fsq_agent/playground/SPEC.md | Serves the local browser playground for Android session setup, dynamic goal/raw-case execution, strict YAML execution, progress polling, screenshots, replay video preview, and report lookup. |
| cli | fsq_agent/cli/SPEC.md | Exposes the public `init`, `run`, `report`, `playground`, strict replay, dynamic-run recording, and local playground workflows. |

## Architecture Diagram

```mermaid
flowchart TD
    CLI[cli] --> Agent[agent]
    CLI --> Core[core]
    CLI --> FSQ[fsq]
    CLI --> Config[config]
    CLI --> Providers[providers]
    CLI --> Models[models]
    CLI --> Report[report]
    CLI --> Playground[playground]
    Agent --> Core[core]
    Agent --> Config[config]
    Agent --> Providers[providers]
    Agent --> Models[models]
    Agent --> Tools[tools]
    Agent --> Observation[observation]
    Agent --> Knowledge[knowledge]
    Agent --> Skills[skills]
    Agent --> Report[report]
    Config --> Models
    Providers --> Config
    Providers --> Models
    Tools --> Models
    Observation --> Models
    Knowledge --> Models
    FSQ --> Models
    Skills --> Models
    Report --> Models
    Core --> Models
```

## Development Rules

- Each module exposes public symbols only from `__init__.py` using explicit `__all__`.
- Internal implementation files are prefixed with `_`.
- Shared data structures and exceptions live only in the `models` module.
- Module imports must follow the DAG in the architecture diagram.
- Provider construction lives in `providers`; `core` must use provider-neutral protocols and must not import provider/runtime modules.
- Cross-platform local utilities live behind the CommonTool interface in `tools`; platform actions and AI assertions belong to harnesses.
- Public interface changes require `SPEC.md` update and user confirmation before implementation.
- `CLAUDE.md` and `AGENTS.md` are agent entry points only. They must point to this root `SPEC.md` and must not duplicate project specification content.
