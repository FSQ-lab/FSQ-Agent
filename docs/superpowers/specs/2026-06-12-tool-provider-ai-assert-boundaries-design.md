# Tool, Provider, And AI Assertion Boundary Design

Date: 2026-06-12

## Goal

Define a reviewed design for agent-visible tools and LLM provider ownership.

The runtime should expose tools in two explicit families:

1. Platform harness tools supplied by the active platform harness. These tools operate on the system under test and own platform assertions such as Android `assertWithAI`.
2. CommonTool core capabilities supplied by a cross-platform common tool interface. These tools provide local runtime utilities such as scoped file IO, allowlisted environment or secret reads, bounded artifact lookup, and pure waits.

The same Azure OpenAI or GitHub Copilot model provider configuration should be reusable by the main agent loop, pre-planner, verifier, and platform AI assertion evaluators. Provider construction should move out of the `agent` module into a shared `providers` module.

## Scope

In scope:

- Introduce a `providers` module as the shared owner of Azure OpenAI and GitHub Copilot provider construction, authentication, endpoint selection, token cache behavior, and Responses API access.
- Introduce an SDK-neutral CommonTool interface in the `tools` module, plus an OpenAI Agents SDK adapter for the agent runtime.
- Keep the confirmed CommonTool core set: `read_file`, `write_file`, `get_runtime_secret`, `search_artifact`, `read_artifact_slice`, and `wait_ms`.
- Reclassify `publish_progress` as an agent-runtime internal tool rather than a public CommonTool capability.
- Remove `run_cli_tool` and optional SDK `shell` from the future tool contract.
- Move AI visual assertion behavior out of CommonTool. Android `assertWithAI` should be a platform assertion operation exposed by `AndroidHarness` when an AI assertion evaluator is configured.
- Allow authored `assertWithAI` in all execution modes, including strict-core mode, when a provider-backed evaluator is available.
- Preserve platform artifact capture as a harness responsibility and preserve bounded artifact read/search as a CommonTool responsibility.

Non-goals:

- Do not implement code from this design document before `SPEC.md` updates are confirmed.
- Do not update root or module `SPEC.md` files in this design step.
- Do not design every future platform harness. Android is the first platform target for AI assertion behavior.
- Do not add a separate AI assertion model override in the first design cycle. AI assertion should reuse the configured `openai_agents` provider and model.
- Do not introduce AI recovery, locator fallback, testcase mutation, or hidden self-healing as part of `assertWithAI`.

## Existing Context

The current root specification defines these relevant modules:

- `config` loads runtime, model provider, harness, driver, strict-core, local tool, and workspace configuration.
- `tools` currently provides local CLI, file, artifact, wait, secret, progress, visual assertion, and optional shell utility tools for the SDK runtime.
- `core` owns the `HarnessInterface`, Android harness, driver contracts, and deterministic strict-core execution contracts.
- `agent` currently constructs OpenAI-compatible provider clients, assembles local utility tools, assembles harness-generated platform tools, runs OpenAI Agents SDK, and runs final verification.

Current implementation observations:

- `OpenAIAgentsRuntime` directly constructs Azure OpenAI or GitHub Copilot `AsyncOpenAI` clients.
- GitHub Copilot provider construction lives in `fsq_agent.agent._copilot_provider`.
- `AgentsToolFactory` hard-codes local SDK tools including `submit_visual_assertion`, `run_cli_tool`, `read_file`, `write_file`, artifact tools, `wait_ms`, `get_runtime_secret`, and optional `shell`.
- `AndroidHarness` currently fails `assertWithAI` with `configuration_error` in deterministic strict-core execution.
- `UiAutomator2AndroidDriver.assert_with_ai` is an unexposed stub and should not own LLM provider behavior.
- Harness action tools are already sourced from `HarnessInterface.action_space()` and adapted by `agent._harness_tools.HarnessToolAdapter`.

## Proposed Architecture

```text
config
  -> loads provider, common-tool, harness, and AI assertion settings

providers
  -> shared Azure OpenAI and GitHub Copilot provider/session construction
  -> OpenAI Agents SDK provider/session access for agent, pre-plan, verifier
  -> direct Responses-style access for provider-backed AI assertion evaluator

tools
  -> SDK-neutral CommonTool contracts and concrete CommonTool providers
  -> AgentsCommonToolAdapter converts CommonTool capabilities into SDK FunctionTool values
  -> no platform actions, no AI assert, no CLI/shell command execution

core
  -> HarnessInterface, AndroidHarness, drivers, runner contracts, evidence policy
  -> AndroidHarness owns Android assertWithAI as a platform assertion operation
  -> AndroidHarness accepts an injected AIAssertionEvaluator-like protocol implementation
  -> core does not construct provider clients or import OpenAI Agents SDK

agent
  -> assembles the dynamic OpenAI Agents SDK runtime
  -> asks providers for the configured model provider/session
  -> adapts CommonTool capabilities and harness action_space into SDK tools
  -> keeps main runner, pre-plan, verifier, event mapping, and report handoff

cli
  -> constructs strict and dynamic runtime dependencies
  -> injects provider-backed AIAssertionEvaluator into AndroidHarness when needed
```

### Provider Ownership

Add a new `fsq_agent/providers` module.

Responsibilities:

- Build Azure OpenAI and GitHub Copilot OpenAI-compatible clients from `Settings`.
- Own GitHub device-code auth, Copilot OAuth token cache path, Copilot token exchange, Copilot plan endpoint selection, and Copilot headers.
- Own Azure OpenAI API key environment lookup and base URL normalization behavior currently tied to the agent runtime.
- Expose a provider/session abstraction reusable by main agent execution, pre-planning, evidence-based verification, and AI assertion evaluator calls.
- Use the configured `openai_agents.provider` and `openai_agents.model` for first-cycle AI assertions.
- Keep provider secret values out of events, reports, and model-visible diagnostics.

The provider abstraction should not require `core` to depend on `agent`. The concrete provider implementation can live in `providers`; `core` should receive only an evaluator protocol object.

### CommonTool Ownership

The `tools` module should move from a hard-coded SDK-tool factory toward an SDK-neutral interface:

```text
CommonToolProvider
  - list_capabilities() -> list[CommonToolCapability]
  - invoke(name, arguments, context) -> CommonToolResult

CommonToolCapability
  - name
  - description
  - params_json_schema
  - safety_class
  - metadata

AgentsCommonToolAdapter
  - converts CommonToolCapability records to SDK FunctionTool objects
  - maps SDK JSON arguments into CommonTool calls
  - records tool_origin="common"
  - applies redaction and artifact policies
```

`CapabilityRegistry` can evolve into `CommonToolRegistry`. It should no longer be centered on CLI/file mixed registration.

Confirmed CommonTool core capabilities:

| Tool | Purpose | Safety boundary |
|---|---|---|
| `read_file` | Read scoped workspace or configured input files. | Must stay inside configured read roots. |
| `write_file` | Write generated files. | Must stay inside configured write root. |
| `get_runtime_secret` | Read configured environment-backed secret values. | Only names in `runtime_secrets.allowed_env_names`; events and reports redact values. |
| `search_artifact` | Search a current-run text artifact by query. | Must stay inside current run directory and return bounded matches. |
| `read_artifact_slice` | Read a bounded slice of a current-run text artifact. | Must stay inside current run directory and enforce max length. |
| `wait_ms` | Wait without touching the platform UI. | Bounded duration; no platform side effects. |

### Tool Disposition

| Current capability | Current role | Future role | Decision |
|---|---|---|---|
| `read_file` | Local SDK tool | CommonTool core | Keep. |
| `write_file` | Local SDK tool | CommonTool core | Keep. |
| `get_runtime_secret` | Local SDK tool | CommonTool core | Keep with allowlist-only env/secret reads. |
| `search_artifact` | Local SDK tool | CommonTool core | Keep for run-local large tool output search. |
| `read_artifact_slice` | Local SDK tool | CommonTool core | Keep for bounded artifact slices. |
| `wait_ms` | Local SDK tool | CommonTool core | Keep. |
| `publish_progress` | Local SDK tool | Agent runtime internal | Keep internal, not CommonTool. |
| `submit_visual_assertion` | Local SDK tool | Replaced by platform AI assert | Remove from public/common tool contract. |
| `run_cli_tool` | Local SDK tool | None | Delete or stop exposing. |
| Optional SDK `shell` | Local SDK tool | None | Delete or stop exposing. |
| `read_knowledge_index` | Pre-plan internal tool | Agent pre-plan internal | Keep internal, not CommonTool. |
| `read_knowledge_page` | Pre-plan internal tool | Agent pre-plan internal | Keep internal, not CommonTool. |
| Harness tools such as `tap_on`, `input_text`, `assert_visible` | Platform action tools | Platform harness tools | Keep outside CommonTool. |
| Future `assert_with_ai` | Missing or incomplete platform assertion | AndroidHarness platform tool | Add or fix. |

### Artifact Boundary

There are two artifact responsibilities and they should stay separate.

Platform/harness artifact capture:

- Produces artifacts such as screenshots and UI trees.
- Uses `HarnessInterface.capture_artifact` and `ArtifactStore`.
- Attaches refs to `HarnessActionResult`, step phase reports, and evidence manifests.
- Is platform or harness owned.

CommonTool artifact lookup:

- Consumes existing text artifacts under the current run directory.
- Provides `search_artifact` and `read_artifact_slice` for bounded readback.
- Is cross-platform and should not decide when screenshots or UI trees are captured.

This keeps platform evidence production separate from model-safe evidence retrieval.

## Android AI Assertion Design

Android `assertWithAI` should become a platform assertion operation. It should not be a CommonTool.

### Runtime Flow

```text
StepRunner or agent harness tool
        |
        v
AndroidHarness.invoke_action(assertWithAI)
        |
        +--> validate AndroidAssertWithAIParams
        +--> capture a fresh screenshot through the Android driver
        +--> persist screenshot artifact when ArtifactStore is available
        +--> call injected AIAssertionEvaluator with prompt, screenshot, and context
        +--> return HarnessActionResult with verdict, metadata, and artifact refs
```

The evaluator should return a structured verdict such as passed, failed, or inconclusive, along with concise evidence text, provider name, model name, and any relevant diagnostic metadata. Shared serializable verdict models should live in `models` if they need to cross module boundaries or appear in evidence/report outputs.

### Dynamic Agent Mode

- The model should call platform tool `assert_with_ai` when it needs Android AI assertion.
- The model should not call public `submit_visual_assertion` because that tool is removed from the future public/common contract.
- The harness tool result should include a bounded verdict JSON and screenshot artifact refs.
- The final verifier should not re-inspect screenshot pixels. It should verify that execution produced an AI assertion verdict and that supplied evidence does not contradict it.

### Strict-Core Mode

This design intentionally changes the current strict-core behavior for authored `assertWithAI`.

- Ordinary strict-core actions remain deterministic.
- Explicit authored `assertWithAI` is allowed to call the configured AI assertion evaluator.
- If a strict case reaches `assertWithAI` and no evaluator or provider credentials are available, the step fails clearly with `failure_category="configuration_error"`.
- This exception must not enable AI recovery, locator fallback, testcase mutation, or hidden alternate execution paths.

### Action-Space Behavior

`AndroidHarness.action_space()` remains the platform action schema source.

For driver-backed actions, schemas continue to come from decorated driver methods.

For `assertWithAI`, the harness should own the schema because the Android driver should not own LLM provider calls. When an evaluator is configured, the harness may add a harness-owned `assert_with_ai` schema with:

- `name="assert_with_ai"`
- `platform="android"`
- `driver_method="assert_with_ai"` or a future schema field that better represents a harness-owned handler
- `fsq_action_name="assertWithAI"`
- metadata showing it is harness-owned and provider-backed

If no evaluator is configured, dynamic runtime should not silently expose a nonfunctional `assert_with_ai` tool. Authored strict steps should still fail clearly when invoked without an evaluator.

### Error Handling

- Invalid `assertWithAI` params: return `configuration_error` and do not capture a screenshot or call the provider.
- Missing evaluator: return `configuration_error`.
- Provider/auth failure: return a failed result with provider name and non-secret diagnostics only.
- Screenshot capture failure: return `observation_error` or `artifact_error` depending on whether capture or persistence failed.
- Evaluator inconclusive: return `status="failed"`, `failure_category="assertion_error"`, and metadata `verdict="inconclusive"`.
- Assertion failed: return `status="failed"`, `failure_category="assertion_error"`.
- Assertion passed: return `status="passed"` with verdict details, provider/model metadata, and screenshot artifact refs.

## Public Behavior

After implementation, an agent run should expose these categories:

- `tool_origin="harness"` for platform actions and platform assertions.
- `tool_origin="common"` for CommonTool core calls.
- `tool_origin="runtime"` for runtime-internal progress events, if progress remains model-visible.

The model-visible platform tool list should come from the active harness. The CommonTool list should come from `CommonToolProvider` or `CommonToolRegistry`. The runtime should fail startup when there is a name conflict between CommonTool, runtime internal tools, and harness action-space tools.

`run_cli_tool`, optional SDK `shell`, and public `submit_visual_assertion` should not appear in the future public tool list.

## Affected Specs Expected To Change

The next spec-driven step should update these files:

- `SPEC.md`: Add the `providers` module and update module table/DAG language for CommonTool and platform tool separation.
- `fsq_agent/providers/SPEC.md`: New module spec for provider factory/session behavior, Azure OpenAI, GitHub Copilot, Responses API access, and provider-backed evaluator support.
- `fsq_agent/config/SPEC.md`: Define provider reuse and AI assertion configuration/readiness behavior. Strict mode should validate provider settings only when `assertWithAI` is present or evaluator use is otherwise required.
- `fsq_agent/models/SPEC.md`: Add shared serializable models for CommonTool capabilities/results and AI assertion verdicts if needed.
- `fsq_agent/tools/SPEC.md`: Redefine the module around CommonTool core and SDK adapter behavior. Remove CLI/shell and public visual assertion from the future contract.
- `fsq_agent/core/SPEC.md`: Update Android `assertWithAI` behavior so it can call an injected evaluator in all modes, while keeping ordinary strict-core behavior deterministic.
- `fsq_agent/agent/SPEC.md`: Move provider construction to `providers`, replace hard-coded local tool assembly with CommonTool adapter usage, and remove public `submit_visual_assertion` behavior.
- `fsq_agent/cli/SPEC.md`: Describe dependency construction for dynamic and strict runs, including provider-backed AI assertion evaluator injection when needed.
- `fsq_agent/report/SPEC.md`: Ensure reports preserve CommonTool, runtime, and harness tool origins, plus AI assertion verdict metadata and screenshot artifact refs.
- `docs/openai-agent-loop.md`: Update explanatory flow so tools are described as CommonTool, runtime internal, and harness platform tools.

## Open Questions Resolved During Discussion

- Overall design approach: Use a public CommonTool capability interface plus SDK adapter. Do not unify CommonTool and platform harness tools into one graph.
- CommonTool core: Keep file read/write, allowlisted env/secret read, bounded artifact search/slice, and wait.
- Artifact tools: Keep `search_artifact` and `read_artifact_slice` as CommonTool capabilities for large run-local tool output lookup.
- Progress tool: Keep `publish_progress` as agent runtime internal, not as CommonTool.
- CLI/shell tools: Delete or stop exposing `run_cli_tool` and optional SDK `shell`.
- Env/secret tool safety: Only read allowlisted names.
- Provider module name: Use `providers`.
- AI assertion mode: `assertWithAI` may run in all modes when evaluator/provider dependencies are configured.
- AI assertion ownership: Android `assertWithAI` is a platform harness assertion, not a CommonTool.
- AI assertion provider config: First cycle reuses the existing `openai_agents` provider/model configuration.

## Verification Expectations

After SPEC updates and implementation, verification should cover these areas.

CommonTool tests:

- CommonTool registry lists only confirmed CommonTool core capabilities.
- `read_file` and `write_file` preserve configured path boundaries.
- `get_runtime_secret` rejects names outside `runtime_secrets.allowed_env_names` and redacts values in events/reports.
- `search_artifact` and `read_artifact_slice` reject paths outside the current run directory and enforce bounded outputs.
- `wait_ms` returns a bounded wait result and does not call platform actions.
- `run_cli_tool`, optional SDK `shell`, and public `submit_visual_assertion` are absent from CommonTool and SDK-visible public tools.

Provider tests:

- Azure OpenAI provider construction works through `providers` and still uses normalized `/openai/v1/` base URL behavior.
- GitHub Copilot provider construction works through `providers` and preserves device-code auth, OAuth cache, Copilot token exchange, plan endpoint selection, and Responses API behavior.
- Main agent, pre-plan, verifier, and AI assertion evaluator all use the shared provider abstraction.
- Provider diagnostics redact secrets.

Agent runtime tests:

- Runtime asks `providers` for model provider/session instead of directly constructing provider clients.
- SDK tools include CommonTool adapter output, harness action-space tools, and runtime internal progress when enabled.
- Tool-origin metadata distinguishes `common`, `harness`, and `runtime`.
- Tool name conflicts fail startup before the SDK runner begins.
- `submit_visual_assertion` no longer drives image attachment behavior in the future public path.

Android AI assertion tests:

- `AndroidHarness.action_space()` includes harness-owned `assert_with_ai` when an evaluator is configured.
- Dynamic agent mode can call harness `assert_with_ai` and receives a bounded verdict JSON.
- Strict-core authored `assertWithAI` calls the evaluator and records screenshot artifact refs and verdict metadata.
- Missing evaluator/provider config fails with `configuration_error`.
- Invalid assertion params do not call screenshot capture or provider.
- Provider/auth failures do not expose secret values.
- Passed, failed, and inconclusive evaluator verdicts map to clear `HarnessActionResult` values.

Report and verifier tests:

- Reports reconstruct CommonTool and harness tool calls with correct origins.
- AI assertion verdict metadata and screenshot artifact refs appear in reports/evidence.
- Evidence-based verifier treats the AI assertion verdict as execution evidence and does not re-inspect screenshot pixels.

Audit expectations:

- `core` does not directly construct provider clients.
- AI assert is not implemented as a CommonTool.
- Platform tool schemas still come from `HarnessInterface.action_space()`.
- CommonTool does not contain platform actions, CLI, or shell.
- Strict-core's LLM use is limited to explicit authored `assertWithAI` evaluator calls.
- No hidden AI recovery, locator fallback, or testcase mutation is introduced.

## Self-Review Notes

- The scope is one SPEC update cycle: provider ownership, CommonTool boundary, and Android AI assertion ownership.
- The design intentionally calls out the strict-core behavior change for `assertWithAI` instead of hiding it as an implementation detail.
- The design keeps platform artifact capture separate from CommonTool artifact read/search.
- The design has no placeholder requirements or unresolved choices.
- The design does not instruct implementation before SPEC confirmation.
