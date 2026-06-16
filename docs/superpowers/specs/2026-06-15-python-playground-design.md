# Python Playground Design

## Goal

Add an fsq-agent playground inspired by Midscene's playground flow, implemented primarily in Python. The playground should let a local operator open a browser page, inspect runtime/device status, start an Android-backed session, submit a natural-language goal for dynamic execution, watch run progress, view the latest screenshot when available, and open generated reports.

## Midscene Reference Summary

Midscene separates playground concerns into a reusable service layer and a UI layer:

- `packages/playground/src/server.ts` owns the local HTTP service, active session state, one-task-at-a-time locking, runtime metadata, action execution, task progress polling, screenshots/MJPEG, manual interaction, config updates, and static SPA serving.
- `packages/playground/src/platform.ts` defines platform descriptors and session-manager contracts. Concrete packages such as `packages/android-playground/src/platform.ts` inject Android device discovery, session creation, scrcpy preview metadata, and sidecars without hard-coding Android behavior into the common server.
- `packages/playground/src/sdk/index.ts` and the adapters hide local-vs-remote execution differences from the UI.
- `packages/playground-app/src/PlaygroundApp.tsx` builds a two-panel experience: conversation/control on the left and live preview on the right.
- The UI controller polls `/status`, `/runtime-info`, `/session/setup`, creates sessions, applies AI config, submits `/execute`, polls `/task-progress/:requestId`, and refreshes preview data.

The fsq-agent version should borrow this shape, not the TypeScript/Nx/React implementation details.

## Scope

Implement a first Python playground with:

- A new Python module, tentatively `fsq_agent.playground`.
- A CLI command, tentatively `fsq-agent playground --config PATH --workspace PATH --host HOST --port PORT --open-browser/--no-open-browser`.
- A local HTTP server implemented with Python standard library APIs in the first batch, to avoid adding FastAPI/Flask unless the API grows.
- Static HTML/CSS/JavaScript assets served from package data.
- JSON endpoints modeled after Midscene's flow: health/status, session setup, create/destroy session, runtime info, execute goal, task progress, screenshot fallback, and report lookup/open metadata.
- Android session setup based on existing fsq-agent configuration and local ADB discovery.
- Dynamic goal execution by calling existing `FsqAgent.from_settings(settings).run(Task(...), event_sink=...)`.
- One active execution at a time per server process.
- Progress capture from `RunEvent` values and final `TaskResult`/report paths.

## Non-Goals

- Do not copy Midscene's React app, Nx build chain, SDK package structure, or report visualizer.
- Do not implement MJPEG/scrcpy streaming in the first Python batch. A screenshot polling endpoint is enough for initial utility.
- Do not add a separate local model/runtime loop. Use existing fsq-agent dynamic execution.
- Do not expose shell execution or arbitrary file operations through the playground.
- Do not mutate source FSQ cases from the playground.
- Do not bypass existing provider/config/secret validation.

## Proposed Architecture

### Module Ownership

Add `fsq_agent.playground` as an entry-layer module. It may depend on `models`, `config`, `agent`, `core`, and `report`, similar to `cli`, but no existing leaf module should depend on it.

Suggested internal files:

- `__init__.py`: public exports only.
- `_server.py`: local HTTP server, route dispatch, JSON helpers, static file serving, lifecycle.
- `_state.py`: in-memory session and task state, locks, progress/event storage.
- `_android.py`: ADB target discovery and Android session metadata helpers.
- `_execution.py`: dynamic goal execution adapter around `FsqAgent.run`.
- `static/index.html`, `static/playground.css`, `static/playground.js`: lightweight browser UI.
- `SPEC.md`: module contract.

### CLI Ownership

Update `cli` with one public command:

```text
fsq-agent playground --config PATH --workspace PATH --host 127.0.0.1 --port 8765 --open-browser
```

The command loads settings, constructs the playground server, starts it, prints the local URL, optionally opens the browser, and blocks until interrupted.

### API Shape

Initial endpoints should be intentionally small:

| Endpoint | Purpose |
|---|---|
| `GET /status` | Server health, server id, busy flag. |
| `GET /session` | Current session state. |
| `GET /session/setup` | Android target selection schema and discovered ADB devices. |
| `POST /session` | Create/select an Android session for one device. |
| `DELETE /session` | Clear active session metadata when no task is running. |
| `GET /runtime-info` | Platform, app id presence, selected device id, preview capabilities, last run summary. |
| `POST /execute` | Start one dynamic goal run. Body contains `goal` and optional metadata. |
| `GET /task-progress/{request_id}` | Return captured `RunEvent` summaries and final result when done. |
| `GET /screenshot` | Return latest screenshot as base64 if the active Android backend can capture one. |
| `GET /reports/{run_id}` | Return stored report metadata or report content path resolution. |

The first `POST /execute` can run synchronously in a background thread owned by the server and immediately return a `request_id`; the browser polls progress. Only one request may run at a time, returning HTTP 409 for concurrent execution.

### UI Shape

The first screen should be the usable playground, not a landing page:

- Left panel: connection/session setup, goal input, run button, stop/status placeholder, progress event list, final result/report link.
- Right panel: screenshot preview with refresh/polling, runtime metadata, selected Android device.
- Offline/error states should be visible without explanatory marketing copy.

The UI should use compact, operational styling and avoid external build tools. Plain HTML/CSS/JavaScript is acceptable for the first batch because fsq-agent is currently a Python package without a frontend toolchain.

## Python Feasibility

Python is feasible for the first implementation because fsq-agent already owns the important backend pieces:

- `FsqAgent.run` provides dynamic execution, event emission, verification, and report generation.
- `config` owns provider/runtime validation and Android settings.
- `core` owns Android harness and screenshot-capable artifact capture paths.
- The standard library can serve local HTML and JSON endpoints well enough for a single-user local playground.

Python is weaker than Midscene's TypeScript stack for:

- Rich React component reuse and complex client state.
- Browser-native streaming integrations such as scrcpy/WebCodecs.
- Sharing schema validation logic between server and UI.

Those are not blockers for a first fsq-agent playground. If later requirements include live scrcpy video, drag/tap overlay controls, or a reusable SDK package, it may be worth adding a small TypeScript frontend or a web framework. For the requested first implementation, Python remains the recommended backend implementation.

## Error Handling And Safety

- Configuration failures should be returned as JSON errors and shown in the UI without exposing secrets.
- `POST /execute` must fail before external UI action when no session/device/config is available.
- Concurrent task starts must return HTTP 409.
- Runtime secret values must never appear in endpoint responses, static assets, progress events, or report previews.
- The server should bind to `127.0.0.1` by default.
- Static serving must reject path traversal and serve only package-owned assets.

## Affected Specs

- Root `SPEC.md`: add the `playground` module to the module table and architecture diagram.
- `fsq_agent/playground/SPEC.md`: define module purpose, dependencies, public API, internal structure, error handling, and design decisions.
- `fsq_agent/cli/SPEC.md`: add the `playground` command and dependency on the `playground` module.
- `pyproject.toml`: include static package assets in wheel metadata if implementation stores assets under `fsq_agent/playground/static`.

## Verification Expectations

- Unit tests for route JSON behavior, static path safety, one-task locking, session setup parsing, and progress state.
- Unit tests for ADB output parsing independent of a real Android device.
- CLI test that `fsq-agent playground` wires options into the server launcher without starting a long-running real server.
- A lightweight smoke check that the static HTML contains the expected app shell and can call `/status`.
- Existing test suite should remain passing.

## Resolved Questions

- Use Python first: yes, because the initial value is a local fsq-agent execution UI rather than Midscene-equivalent streaming and React extensibility.
- Reuse existing execution: yes, dynamic playground execution wraps `FsqAgent.run` rather than implementing a new agent loop.
- First preview mode: screenshot polling/fallback only; live scrcpy/MJPEG is a later SPEC cycle.
