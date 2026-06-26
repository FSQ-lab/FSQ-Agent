# Playwright Web Platform Design

Date: 2026-06-26

## Goal

Integrate Playwright as FSQ-Agent's first Web platform backend while following the existing harness design. Web support must work through the same capability registry, `HarnessInterface`, `StepRunner`, evidence recorder, dynamic Agent SDK tool exposure, strict FSQ replay, and playground execution surfaces already used by Android.

The design is a platform extension, not an execution-core rewrite. `StepRunner` continues to execute canonical capabilities through `HarnessInterface` and metadata-driven routing. Web behavior lives behind a new `WebHarness` and `PlaywrightWebDriver`, with Web-specific parameter models, action catalog entries, artifact capture, configuration, runtime skill guidance, and entry-layer construction.

## Feasibility

Feasibility is high.

Local evidence supporting this:

- `HarnessInterface` is already platform-neutral and exposes context, action space, before/after hooks, action invocation, artifact capture, and error classification.
- `HarnessPlatform` already includes `web` in shared models.
- `capabilities` already states that future Web platforms should add catalogs and reuse `platform_driver_capability` rather than creating platform-specific decorator semantics.
- `core` already states that future Web, desktop, and iOS platforms should add platform action catalogs and reuse catalog-backed declaration helpers.
- Android already demonstrates the intended split: platform harness, backend driver protocol, catalog-backed driver declarations, default capability definitions, artifact capture, and entry-layer harness construction.

The main required architecture change is not in `StepRunner`; it is in platform-aware registry bootstrap and entry-layer harness selection. The current bootstrap registers Android capabilities unconditionally. Web support should register CommonTool capabilities plus only the selected platform's capabilities.

## Scope

In scope for the first Web platform cycle:

- Add Web/Playwright configuration under `harness.platform: web` and `harness.web.backend: playwright`.
- Add Web capability parameter models, action catalog entries, replay aliases, and capability discovery metadata.
- Add `WebHarness` and `PlaywrightWebDriver` implementations that satisfy the existing runner-facing harness and driver boundaries.
- Support dynamic LLM execution, strict YAML execution, and playground execution for Web.
- Add `knowledge/skills/web-harness.md` so the Agent SDK receives platform-specific tool-selection and argument guidance.
- Keep evidence capture, post-action delay, sensitivity, replay, and event/report metadata driven by capability definitions and `StepRunner`.
- Add focused unit tests and fake Playwright-driver tests that do not require a real browser by default.

## Non-Goals

- Do not rewrite `StepRunner`, `StepSequenceRunner`, evidence recording, report generation, or verifier contracts.
- Do not add AI locator self-healing, action repair, testcase mutation, or recovery-mode execution.
- Do not add cloud browser providers, remote browser grids, browser extension control, Browser MCP, or CDP attach as execution backends in this cycle.
- Do not expose Web through Android-style aliases such as `tapOn` and `inputText` as the primary API.
- Do not require real Playwright browsers during ordinary unit tests.
- Do not make skills executable. `web-harness.md` is advisory Agent SDK prompt context only.

## Approaches Considered

### Approach A: Dynamic-Only Web Support

Expose Playwright tools only to the dynamic agent. This is smaller, but it leaves strict replay and playground behind and immediately creates platform drift between exploration and deterministic execution.

Decision: rejected for this scope.

### Approach B: Platform-Selected Registry With Web-Native Actions

Build the capability registry from CommonTool capabilities plus only the active platform's default capability definitions. Web receives its own aliases such as `navigateTo`, `clickOn`, and `typeText`. Strict parsing resolves commands against the selected platform snapshot. Dynamic SDK tools come from the active harness `action_space()`.

Decision: recommended and confirmed.

### Approach C: Namespaced Global Registry

Register Android and Web together with unique names such as `android_tap_on` and `web_click_on`. This avoids platform-selected bootstrap but makes user-authored YAML and dynamic tool names noisier, while still requiring entry-layer platform selection for harness construction.

Decision: rejected for first batch.

## Proposed Design

### Platform-Selected Capability Registry

The package capability bootstrap should become platform-aware:

```python
build_capability_registry(platform=settings.harness.platform, include_ai_assertion=True)
```

It should register CommonTool capabilities plus the selected platform's default capability definitions. Android registrations remain unchanged when `platform="android"`; Web registrations are used when `platform="web"`.

This avoids future name and alias conflicts. Web can expose native canonical names and aliases such as `navigate_to`/`navigateTo`, `click_on`/`clickOn`, and `type_text`/`typeText` without registering Android capabilities in the same registry. Strict FSQ parsing already consumes a registry snapshot, so platform-specific parsing stays entry-owned rather than parser-owned.

### Web Action Set

Playwright's LLM-facing MCP design is the closest reference point for the Web harness action surface. It is accessibility-snapshot driven, uses exact target references from the page snapshot or unique selectors, keeps screenshots as observation/evidence rather than the normal action-planning substrate, and separates core automation from opt-in network, storage, devtools, coordinate, PDF, and testing capability groups. FSQ-Agent should follow that shape while preserving FSQ's own strict replay and assertion contracts.

First-batch Web capabilities should use Web-native aliases inspired by Playwright MCP core automation:

| Alias | Canonical name | Step kind | Evidence | Purpose |
|---|---|---|---|---|
| `navigateTo` | `navigate_to` | `setup` or `action` | yes | Navigate current page to a URL. |
| `navigateBack` | `navigate_back` | `action` | yes | Go back to the previous page. |
| `clickOn` | `click_on` | `action` | yes | Click a visible Web target. |
| `typeText` | `type_text` | `action` | yes | Type or fill text into an editable Web target, with optional submit/slow typing semantics. |
| `selectOption` | `select_option` | `action` | yes | Select one or more values in a dropdown-like target. |
| `hoverOn` | `hover_on` | `action` | no | Hover over a Web target. |
| `pressKey` | `press_key` | `action` | yes | Send a semantic keyboard key. |
| `waitFor` | `wait_for` | `action` | no | Wait for text to appear, disappear, or for a bounded time to pass. |
| `takeScreenshot` | `take_screenshot` | `observation` | no | Capture a screenshot artifact for evidence/debugging, not for target selection. |
| `pageSnapshot` | `page_snapshot` | `observation` | no | Return an accessibility/DOM-oriented page snapshot for planning/debugging. |
| `assertVisible` | `assert_visible` | `assertion` | no | Assert a target is visible. |
| `assertNotVisible` | `assert_not_visible` | `assertion` | no | Assert a target is absent or hidden. |
| `assertText` | `assert_text` | `assertion` | no | Assert page or element text contains/equals expected text. |
| `assertWithAI` | `assert_with_ai` | `assertion` | no | Explicit visual/page assertion through the configured AI evaluator. |

Decision: Web observation uses canonical `page_snapshot` with alias `pageSnapshot`. It should not reuse Android's `ui_tree`/`uiTree` naming because Web has its own harness and driver interface.

Not first-batch harness actions: arbitrary JavaScript/evaluate, unsafe Playwright code execution, network request inspection/mocking, storage manipulation, tab management, drag/drop, file upload, browser close/resize, PDF, coordinate/vision tools, and generated Playwright test code. These can become separate opt-in capability groups after SPEC review if FSQ-Agent needs them.

### Web Parameter Models

Shared cross-module Web models belong in `fsq_agent.models`, following the existing Android pattern. Suggested first-batch models:

- `WebLocator`: optional `role`, `name`, `text`, `label`, `placeholder`, `testId`, `css`, and `xpath` fields, with at least one populated field required when no semantic `target` is supplied.
- `WebNavigateToParams`: required `url` string, optional `wait_until` constrained to Playwright-safe lifecycle states.
- `WebNavigateBackParams`: no fields for the first batch.
- `WebClickOnParams`: required snapshot `target` string or `locator`, optional human-readable `element`, `double_click`, `button`, and `modifiers` fields.
- `WebTypeTextParams`: required `text` plus snapshot `target` or `locator`, optional human-readable `element`, `submit`, and `slowly` fields.
- `WebSelectOptionParams`: required `values` plus snapshot `target` or `locator`, optional human-readable `element`.
- `WebHoverOnParams`: required snapshot `target` or `locator`, optional human-readable `element`.
- `WebPressKeyParams`: required `key` string.
- `WebWaitForParams`: exactly one bounded wait condition from `time`, `text`, or `text_gone`.
- `WebTakeScreenshotParams`: optional snapshot `target` or `locator`, optional human-readable `element`, optional image `type`, and optional `full_page`. ArtifactStore owns filenames/paths.
- `WebAssertVisibleParams` and `WebAssertNotVisibleParams`: `target` or `locator`, optional assertion metadata.
- `WebAssertTextParams`: optional `target` or `locator`, plus text predicate supporting `contains` and `equals`.
- `WebPageSnapshotParams`: optional snapshot `target` or `locator`, optional `depth`, and optional `boxes`. ArtifactStore owns filenames/paths.
- `WebAssertWithAIParams`: required `prompt`, optional assertion metadata.

These models should forbid unexpected fields and serialize with `model_dump(mode="json", exclude_none=True)`. Runtime-only metadata such as evidence policy, timeout, source refs, and replay provenance stays on `ExecutableStep`.

### Web Harness and Playwright Driver

Add a Web harness sub-slice under `fsq_agent.core.harness`:

- `WebDriverInterface`: protocol for typed Web backend methods and observations.
- `WebHarness`: runner-facing harness implementation satisfying `HarnessInterface`.
- `PlaywrightWebDriver`: optional backend that wraps Playwright sync APIs.
- Web driver declaration helper/catalog wiring backed by existing `platform_driver_capability`.
- Default Web capability definitions used for registry bootstrap without launching a real browser.

`WebHarness` should mirror the Android harness shape:

- `get_context()` returns `HarnessContext(platform="web", session_id=..., current_url=..., screen_size=..., metadata={"backend": "playwright", ...})`.
- `action_space()` discovers decorated Playwright driver methods and optionally appends `assert_with_ai` when an evaluator is injected.
- `invoke_action()` validates params with the capability parameter model, routes harness-owned AI assertion to the harness, and routes driver capabilities to the Playwright driver method from metadata.
- `capture_artifact("screenshot")` writes PNG bytes from `page.screenshot()`.
- `capture_artifact("page_snapshot")` writes the Web page snapshot JSON. The SPEC update should add or confirm a `page_snapshot` evidence artifact kind rather than mapping Web snapshots through Android-oriented `ui_tree` naming.
- `classify_error()` maps Playwright timeouts and target misses to existing failure categories.

`PlaywrightWebDriver` should own Playwright-specific mechanics:

- Lazy import Playwright so registry bootstrap and strict parsing do not require Playwright to be installed.
- Launch or attach to a browser/page according to Web settings.
- Resolve targets in a stable priority order: exact snapshot target reference or unique selector first; explicit role/name, label, placeholder, test id, text, CSS, and XPath locators next; semantic target fallback last.
- Return structured `HarnessActionResult`-compatible dicts for passed, target missing, assertion failure, timeout, and configuration errors.

### Configuration

Extend settings models and validation:

```yaml
harness:
  platform: web
  web:
    backend: playwright
    browser: chromium
    headless: false
    base_url: null
```

Recommended first-batch fields:

- `backend: Literal["playwright"]`
- `browser: Literal["chromium", "firefox", "webkit"] = "chromium"`
- `headless: bool = false`
- `base_url: str | None = None`
- Optional viewport fields only if needed by tests or playground screenshot stability.

Local user values that vary by machine should use environment variables when appropriate. A future SPEC update should decide whether `FSQ_WEB_BASE_URL` or YAML-owned `base_url` is preferred. For first-batch Web tests, either `base_url` or fully qualified `navigateTo.url` can be sufficient.

Add a `web` optional dependency in `pyproject.toml`:

```toml
web = [
    "playwright>=1.0.0",
]
```

Browser installation remains an operator setup step, for example `python -m playwright install chromium`, and should be reported clearly when missing.

### Dynamic Agent SDK Execution

`OpenAIAgentsRuntime` should build the active harness from `settings.harness.platform`:

- Android path remains unchanged.
- Web path constructs `PlaywrightWebDriver` and `WebHarness` with an `ArtifactStore` rooted at the run directory and an AI assertion evaluator when available.

SDK tool exposure remains registry/harness-driven. The runtime should not inspect Web decorator internals or Playwright APIs. Tool conversion continues to use `harness.action_space()` and the `StepRunner`-backed adapter.

### Web Harness Skill

Add `knowledge/skills/web-harness.md` and configure it for Web runs. The skill should mirror the Android skill structure and include:

- Scope: use when `harness.platform` is Web.
- Tool selection table mapping Web testing semantics to `navigate_to`, `navigate_back`, `click_on`, `type_text`, `select_option`, `hover_on`, `press_key`, `wait_for`, `take_screenshot`, assertion tools, page snapshot, `wait_ms`, and `assert_with_ai`.
- Locator priority: role/name and labels first, then test id or stable CSS, XPath only as a last resort.
- Assertion rules: required verify/assert/check/ensure language must use assertion tools, not narrative over observations.
- Waiting rules: use `wait_ms` or Playwright-backed navigation/action readiness; do not use repeated clicks as waits.
- Argument rules: follow active tool schemas, avoid backend-only Playwright fields, and do not mix locator styles when one stable locator is enough.
- Error recovery: rebuild invalid payloads from schema, inspect fresh `page_snapshot` after target misses, and retry the same semantic action before fallback.
- AI assertion rules: wait/observe first, then call `assert_with_ai`; do not treat screenshot paths alone as verdicts.

Configuration should load `automation-basics` plus the platform-specific skill. Example Web config should include:

```yaml
agent_context:
  knowledge:
    skills:
      items:
        - name: automation-basics
          description: Semantic action and evidence guidance for local runs.
          kind: markdown
          path: automation-basics.md
          required: true
        - name: web-harness
          description: Web harness action selection and recovery guidance.
          kind: markdown
          path: web-harness.md
          required: true
```

The default Android example should continue to use `android-harness`. If a single config supports platform switching, operators should change both `harness.platform` and the platform-specific skill item together.

### Strict FSQ Execution

Strict execution should use the platform-selected registry snapshot and platform-selected harness constructor:

- For Android strict cases, behavior remains unchanged.
- For Web strict cases, `.codex.yaml` commands resolve through Web replay aliases and execute through `WebHarness`.
- `FsqExecutableStepAdapter` remains platform-agnostic and consumes only the registry snapshot.
- Runtime-secret refs continue to resolve in CLI/playground strict entry code before final parameter validation.
- Strict Web cases should require either a full URL in `navigateTo` or a configured base URL policy recorded in SPEC.

The CLI helper names should become platform-neutral where currently named Android, for example replacing `_build_strict_android_harness` with a platform-dispatching strict harness builder.

### Playground Execution

The playground should support Web alongside Android rather than creating a separate Web-only server.

Required changes:

- Runtime info should report the active platform and Web backend/browser/headless/base URL fields when configured.
- Session APIs that are Android-specific should either return platform-specific unavailable responses for Web or be generalized after SPEC review. The first Web cycle can keep ADB setup endpoints Android-only while allowing `/execute`, progress, screenshot, replay frames, replay video, and report lookup for Web.
- Dynamic execution should instantiate `FsqAgent` with Web settings and the Web skill configuration.
- Strict execution should construct the Web harness through the same platform-dispatching strict harness builder used by CLI.
- Screenshot preview should call the active harness/driver path. For Web this means page screenshot bytes; for Android it remains device screenshot bytes.

### Reports, Recording, and Verification

Existing reports and dynamic recording should continue to consume normalized capability events. Web capabilities with `ReplayPolicy(kind="fsq_command")` can be recorded into generated strict YAML using their Web aliases.

Report and recording code must not infer platform semantics from tool names. They should use capability metadata already emitted by `StepRunner`: canonical name, aliases, executor kind, step kind, platform, backend, replay policy, status, safe replay params, and artifact refs.

## Python Architecture Level

- `models`, `capabilities`, `skills`, and `fsq` remain Level 2 Simple Package modules. They gain Web contracts, catalog metadata, skill content, and registry-snapshot-driven parsing behavior without orchestration responsibilities.
- `core`, `agent`, `cli`, and `playground` remain Level 3 Layered Application modules. They coordinate Web harness construction, dynamic/strict execution, Playwright lifecycle, and entry-layer behavior.
- No Clean Architecture, Repository, Unit of Work, or DDD patterns are justified. The existing harness/driver protocol split is the right abstraction level.

## Affected Specs Expected To Change

The follow-up `spec-driven` cycle should update these specs before implementation:

- Root `SPEC.md`: note Web/Playwright as a supported platform and update module summaries if needed.
- `fsq_agent/models/SPEC.md`: Web parameter models, Web harness settings, Web action definitions, and the `page_snapshot` observation/artifact contract.
- `fsq_agent/capabilities/SPEC.md`: Web action catalog usage through existing platform catalog helpers.
- `fsq_agent/core/SPEC.md`: `WebHarness`, `WebDriverInterface`, `PlaywrightWebDriver`, default Web capability definitions, artifact capture, and lazy backend import behavior.
- `fsq_agent/config/SPEC.md`: `harness.platform` supports `android` and `web`; `harness.web` configuration shape and validation.
- `fsq_agent/agent/SPEC.md`: platform-dispatching harness construction and Web skill loading expectations.
- `fsq_agent/cli/SPEC.md`: platform-selected registry/harness strict execution and Web strict validation rules.
- `fsq_agent/playground/SPEC.md`: active-platform execution, Web runtime metadata, screenshot preview, and Android-only session endpoint behavior.
- `fsq_agent/fsq/SPEC.md`: Web command examples and confirmation that parsing remains registry-snapshot-driven.
- `fsq_agent/skills/SPEC.md`: Web harness skill expectations if module docs need explicit mention.

## Open Questions Resolved

- Scope includes dynamic LLM run, strict YAML run, and playground execution.
- Web first batch uses Web-native aliases rather than Android aliases.
- Web observation uses canonical `page_snapshot` with alias `pageSnapshot`; it does not reuse Android `ui_tree`/`uiTree` naming.
- The Agent SDK needs a `web-harness.md` skill, not only Web tool schemas.
- Playwright should be integrated as a platform backend behind the existing harness design, not as a runner special case.
- Capability registry construction should become platform-selected to avoid cross-platform name and alias conflicts.

## Verification Expectations

Focused verification for the implementation cycle should include:

- Model tests for Web parameter validation and settings validation.
- Capability tests proving Web catalog-backed declarations produce the expected canonical names, aliases, replay policies, platform/backend metadata, evidence flags, and schemas.
- Web harness tests with a fake Playwright driver/page proving dispatch, validation failures, target misses, artifact capture, and AI assertion evaluator boundaries.
- Registry bootstrap tests proving Android-only and Web-only platform registries include CommonTool plus the selected platform capabilities and do not expose the other platform.
- FSQ adapter tests proving Web aliases resolve from a Web registry snapshot and Android aliases still resolve from an Android registry snapshot.
- CLI strict tests using fake harness injection or narrow helpers to verify platform dispatch without launching a real browser.
- Agent runtime tests proving Web harness `action_space()` becomes SDK tools and `web-harness.md` can be loaded as configured skill context.
- Playground tests proving Web runtime info, execution dispatch, screenshot preview, and report lookup behavior where practical with fakes.

Suggested commands after implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_models.py tests/test_config.py tests/test_capabilities.py tests/test_android_harness.py
.\.venv\Scripts\python.exe -m pytest tests/test_fsq.py tests/test_cli_core_execution.py tests/test_openai_runtime.py tests/test_playground.py
```

Real browser smoke validation should be a separate opt-in check because it requires installing Playwright browsers and may open a visible browser when `headless: false`.

## Self-Review

- The design keeps implementation out of this phase and does not update `SPEC.md` files.
- The design is one coherent subsystem: adding Web/Playwright support to the existing harness platform boundary.
- Runner behavior remains metadata-driven and platform-neutral.
- Dynamic, strict, and playground entry surfaces are covered.
- The required Web harness skill for Agent SDK context is included.
- No unresolved placeholder text remains.

## Handoff Notes

This design document is not the implementation source of truth. The next phase must update and confirm the affected `SPEC.md` files first. Implementation should follow confirmed SPEC files, not this design document or chat history.