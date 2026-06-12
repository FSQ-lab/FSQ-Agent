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

## Module Table

| Module | SPEC | Purpose |
|---|---|---|
| models | fsq_agent/models/SPEC.md | Owns shared domain models, result types, and exceptions. |
| config | fsq_agent/config/SPEC.md | Loads and validates runtime, provider, harness/driver, strict-core, common tool, and workspace configuration. |
| providers | fsq_agent/providers/SPEC.md | Builds shared Azure OpenAI and GitHub Copilot provider sessions for agent runs, verifier/pre-planner calls, and provider-backed AI assertion evaluators. |
| tools | fsq_agent/tools/SPEC.md | Provides SDK-neutral CommonTool capabilities and the OpenAI Agents SDK adapter for file, artifact, wait, and allowlisted runtime-secret utilities. |
| observation | fsq_agent/observation/SPEC.md | Persists run event timelines; screenshots, UI trees, and other observations are represented by harness or CommonTool artifact refs. |
| knowledge | fsq_agent/knowledge/SPEC.md | Loads private element history and application knowledge. |
| fsq | fsq_agent/fsq/SPEC.md | Loads FSQ AI Test DSL YAML cases and converts parsed cases into deterministic strict-core executable steps. |
| skills | fsq_agent/skills/SPEC.md | Loads automation skill instruction bundles and skill file metadata. |
| report | fsq_agent/report/SPEC.md | Generates LLM task reports, strict-core evidence reports, and resolves stored reports by run id. |
| core | fsq_agent/core/SPEC.md | Defines shared execution-core orchestration boundaries, StepRunner protocol, harness interface, and evidence coordination. |
| agent | fsq_agent/agent/SPEC.md | Orchestrates dynamic goal/reference execution through OpenAI Agents SDK, verification, retry, and report generation. |
| cli | fsq_agent/cli/SPEC.md | Exposes the public `init`, `run`, and `report` command line workflows. |

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
