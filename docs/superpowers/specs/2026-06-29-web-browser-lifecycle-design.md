# Web Browser Lifecycle Design

Date: 2026-06-29

## Goal

Align the Web platform lifecycle model with the Android platform model by making browser startup and shutdown explicit capabilities instead of implicit driver construction side effects.

The Web harness should expose `startBrowser` and `closeBrowser` so dynamic LLM tasks and strict FSQ cases can represent workflows that open, close, and later reopen the browser during one task. The Web driver should no longer launch a browser merely because the runtime constructed `PlaywrightWebDriver`.

## Scope

In scope for this design cycle:

- Add Web lifecycle capabilities with canonical names `start_browser` and `close_browser`, authored aliases `startBrowser` and `closeBrowser`, and setup/teardown step kinds.
- Make `PlaywrightWebDriver` lazy: construction records configuration and prepares backend ownership state, but does not launch Playwright, Chromium, a browser context, or a page until `start_browser` is invoked.
- Keep `startBrowser` idempotent. If a browser/page is already active, the capability returns success and reuses the current browser/page.
- Let `closeBrowser` close the active Playwright context/browser/session when one is active, reset driver state so a later `startBrowser` can create a new browser/page, and return success when already closed.
- Update Web skill instructions so Web tasks begin with `start_browser` and end with `close_browser` when they own the browser lifecycle.
- Update strict FSQ parsing, dynamic tool exposure, recording, reports, and tests through existing capability metadata paths rather than action-name branches.

## Non-Goals

- Do not add Playwright tab management, browser storage, network interception, devtools, file upload, drag/drop, PDF, generated Playwright code, or JavaScript evaluation.
- Do not add automatic lifecycle command insertion in CLI, agent, FSQ parsing, StepRunner, or StepSequenceRunner.
- Do not make `navigateTo` implicitly start a browser.
- Do not change Android lifecycle semantics in this cycle.
- Do not add a new browser backend or remote browser provider.

## Requirements and Decisions

- Web and Android lifecycle strategy should be consistent: lifecycle is explicit capability behavior, not hidden task orchestration.
- User tasks may include complex flows with multiple browser start and close cycles in the same task.
- `startBrowser` idempotency is confirmed: repeated calls while a browser is active should succeed and reuse the current browser/page.
- Browser startup and shutdown should use the same lifecycle implementation whether invoked by dynamic tools or strict FSQ replay.
- Runtime construction may validate configuration and build the harness/driver object, but it must not open the browser.

## Proposed Design

### Capability Surface

Add Web lifecycle parameter models in `models`:

- `WebStartBrowserParams`: accepts no fields for the first lifecycle batch.
- `WebCloseBrowserParams`: accepts no fields for the first lifecycle batch.

Add Web action definitions:

| Alias | Canonical name | Step kind | Replay | Evidence | Purpose |
|---|---|---|---|---|---|
| `startBrowser` | `start_browser` | `setup` | `fsq_command` | false | Start or reuse the current configured browser/page. |
| `closeBrowser` | `close_browser` | `teardown` | `fsq_command` | false | Close the active browser/page and reset driver state. |

Lifecycle capabilities should not use the default screenshot plus `page_snapshot` capture policy. Before `startBrowser`, there is no page to snapshot. After `closeBrowser`, there is intentionally no page to snapshot. Their tool results are the lifecycle evidence.

### Driver Lifecycle

`PlaywrightWebDriver.__init__` should no longer call `_create_page()` unless a test or caller injects a `page`. It should initialize nullable owned state:

- `_playwright`
- `_browser`
- `_context`
- `page`
- `_executor`
- ownership flags for injected versus driver-created pages

`start_browser(params)` should:

1. Ensure a worker executor exists for owned Playwright operations.
2. If `page` is already active, return a passed result with `already_started: true` and current URL/context metadata.
3. Otherwise lazy-import Playwright, start it, launch the configured Chrome executable, create a context, create a page, store state, and return a passed result with `already_started: false`.

`close_browser(params)` should:

1. If no page/context/browser/playwright is active, return a passed result with `already_closed: true`.
2. Otherwise close owned context/browser and stop Playwright in the same worker thread.
3. Reset `_playwright`, `_browser`, `_context`, and `page` to `None`.
4. Keep the worker executor available for a later `startBrowser` during the same task.
5. Return a passed result with `already_closed: false`.

The existing `close()` method remains a final resource cleanup hook. It should call the same close-browser implementation and then shut down the worker executor. Entry layers may use it for process cleanup, but it must not replace explicit `closeBrowser` task semantics.

For injected fake pages used by tests, the driver should treat the page as already started. `startBrowser` returns idempotent success. `closeBrowser` should not assume ownership of external Playwright resources; tests can verify state through fakes without requiring a real browser.

### Behavior Before Start

All page-dependent Web actions should require an active page. This includes `navigate_to`, `navigate_back`, `click_on`, `type_text`, `select_option`, `hover_on`, `press_key`, `wait_for`, `take_screenshot`, `page_snapshot`, and deterministic assertions.

If such an action is invoked before `startBrowser`, the driver should return a structured failed result with a clear message such as:

```text
Browser is not started. Call startBrowser before Web page actions.
```

The failure should be a normal harness/driver failure, not an implicit browser launch. This keeps dynamic and strict behavior aligned and makes missing lifecycle setup visible in reports.

`context()` must also tolerate the not-started state so StepRunner prepare can run before `startBrowser`. It should return `HarnessContext(platform="web")` with `current_url=None`, configured screen size when known, and metadata such as `browser_started: false`.

### Strict FSQ Execution

Strict Web command support should include:

| FSQ command shape | canonical `action_name` | step kind | params |
|---|---|---|---|
| `startBrowser: {}` | `start_browser` | `setup` | `{}` |
| `closeBrowser: {}` | `close_browser` | `teardown` | `{}` |

`FsqExecutableStepAdapter` should continue to rely on capability metadata for alias resolution, payload validation, and step kind. No parser-specific Web lifecycle branch should be needed beyond SPEC documentation and tests.

Trailing `closeBrowser` steps should be treated like Android trailing `killApp`: `StepSequenceRunner` receives them as teardown steps and executes them even when earlier normal steps fail.

### Dynamic Agent Execution

Dynamic Web tasks should receive `start_browser` and `close_browser` tools from the active Web harness. The runtime should not automatically call either tool.

The Web skill instruction should say:

- Start browser with `start_browser` before the first page action when the task owns a browser workflow.
- Navigate after startup with `navigate_to`; do not treat `navigate_to` as startup.
- Close browser with `close_browser` as the final lifecycle action when the task goal or harness convention requires closing.
- For multi-cycle tasks, call `close_browser` and then `start_browser` again for the next cycle.
- Do not use `Alt+F4`, `Control+W`, or unrelated key presses as browser lifecycle controls.

This makes the agent-facing guidance match the explicit capability surface.

### Recording and Reports

Dynamic recording should record successful `startBrowser` and `closeBrowser` calls through normal `ReplayPolicy(kind="fsq_command")` metadata. The recorder must not invent lifecycle commands when the dynamic run did not execute them.

Reports should treat both lifecycle tools as real harness/driver tool calls reconstructed from structured capability metadata. Runtime setup progress events such as "Harness setup completed" remain runtime provenance and are not lifecycle tool calls.

### Runtime Cleanup

This design separates task semantics from resource cleanup:

- `closeBrowser` is the task-visible lifecycle capability and replayable FSQ command.
- `PlaywrightWebDriver.close()` is a final resource cleanup hook for entry layers and process shutdown.

Implementation may add explicit entry-layer cleanup later, but cleanup must not be recorded as a task command and must not be used by the verifier as proof that the task executed `closeBrowser`.

## Python Architecture

- Architecture level: Level 3 Layered Application for `core`, `agent`, `cli`, and `playground`; Level 2 Simple Package for `models`, `fsq`, and `skills`.
- Public API changes: export `WebStartBrowserParams` and `WebCloseBrowserParams` from `models`; expose `start_browser` and `close_browser` through Web capability metadata and Web harness action space.
- Internal modules: changes should remain in existing private modules such as `models/_core.py`, `core/harness/_web_driver.py`, `core/harness/_playwright_driver.py`, and capability/default-definition helpers.
- Domain boundaries: lifecycle mechanics live in the Web driver; harness routing and validation live in `WebHarness`; ordering remains in `StepSequenceRunner`; parsing remains in `fsq`; prompt guidance remains in skill Markdown.
- Dependency direction: preserve the current DAG. `core` must still import only `models` and `capabilities` among project modules. `models` must not import project modules.
- Rationale: this is a platform capability boundary change, not a new domain model. Existing Level 2/3 architecture is sufficient.

## Affected Specs

Expected SPEC updates in the next SDD step:

- Root `SPEC.md`: Web platform block should mention explicit browser lifecycle capabilities and no implicit browser startup.
- `fsq_agent/models/SPEC.md`: add Web lifecycle parameter models and platform contract text.
- `fsq_agent/core/SPEC.md`: add Web lifecycle capability surface, lazy Playwright startup, not-started behavior, and driver cleanup distinction.
- `fsq_agent/fsq/SPEC.md`: add `startBrowser`/`closeBrowser` command mappings and step kind expectations.
- `fsq_agent/skills/SPEC.md`: update Web harness skill expectations.
- `fsq_agent/agent/SPEC.md` and `fsq_agent/cli/SPEC.md`: clarify dynamic/strict exposure and that entry layers do not inject lifecycle commands.
- `fsq_agent/playground/SPEC.md`: clarify Web runs no longer launch until `startBrowser` and screenshot/session behavior before start.

## Verification Expectations

Focused tests should cover:

- `PlaywrightWebDriver` construction does not import Playwright or launch a browser by default.
- `start_browser` launches only when needed and is idempotent when already started.
- `close_browser` closes owned Playwright resources, is idempotent when already closed, and permits a later `start_browser`.
- Page-dependent actions fail clearly before startup instead of implicitly launching.
- `WebHarness.action_space()` includes `start_browser` and `close_browser` with aliases `startBrowser` and `closeBrowser`.
- Strict FSQ parsing accepts `startBrowser` and `closeBrowser` for Web registries and classifies them as setup/teardown.
- Dynamic recording includes lifecycle commands only when the run executed them.
- Web skill guidance names `start_browser` as the beginning lifecycle action and `close_browser` as the ending lifecycle action.

Suggested focused verification command after implementation:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_playwright_web_driver.py tests/test_web_harness.py tests/test_fsq_loader.py tests/test_cli_core_execution.py
```

Broader verification should include agent/recording tests when lifecycle commands are exposed to dynamic runs.

## Open Questions Resolved

- `startBrowser` while already started: idempotent success, reuse the current browser/page.
- Default Web browser startup during driver construction: remove it; browser startup is explicit.
- `navigateTo` startup behavior: no implicit startup; missing `startBrowser` is a visible failure.
- Lifecycle cleanup in recordings: only user/agent-executed lifecycle capabilities are recorded; final resource cleanup is not recorded.