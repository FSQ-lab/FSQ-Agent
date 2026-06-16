# Module: playground

## Purpose

Serve a local, single-user fsq-agent playground. The playground owns a Python HTTP API and static browser UI for inspecting runtime status, selecting an Android session target, submitting dynamic natural-language goals or raw FSQ YAML references, polling execution progress from `RunEvent` values, viewing a screenshot preview when available, and resolving generated reports.

The playground is an entry-layer convenience surface. It reuses existing fsq-agent execution, configuration, Android harness, event, report, and recording contracts rather than implementing a separate agent loop or platform runner.

## Dependencies

- `models`: Uses `Task`, `TaskResult`, `RunEvent`, report artifacts, and shared configuration/error models.
- `config`: Loads settings and applies the same runtime/provider/strict validation policy used by CLI entry points.
- `agent`: Runs dynamic goal/raw-reference tasks through `FsqAgent.run` and receives live events through an event sink.
- `core`: Uses Android harness/driver capabilities for session metadata and screenshot capture when the configured backend supports it.
- `report`: Resolves generated report paths for completed runs.
- `recording`: Records completed playground dynamic runs into run-local strict replay YAML artifacts using the post-run recorder.

The module must not be imported by `models`, `config`, `providers`, `tools`, `observation`, `knowledge`, `skills`, `fsq`, `core`, `agent`, or `report`. `cli` may import `playground` to expose the public command.

## Public Interface

Target `__init__.py` exports via `__all__`:

- `PlaygroundServer`: Local HTTP server wrapper.
- `PlaygroundServerOptions`: Host, port, open-browser flag, and optional static path overrides for tests.
- `run_playground(settings: Settings, options: PlaygroundServerOptions) -> None`: Blocking entry helper used by the CLI command.

Initial HTTP API:

| Endpoint | Behavior |
|---|---|
| `GET /status` | Return server health, selected session summary, and busy flag. |
| `GET /session` | Return current Android session state. |
| `GET /session/setup` | Return Android setup schema plus discovered ADB targets. |
| `POST /session/auto` | Automatically select/create an Android session when configuration or device discovery has one unambiguous online target. |
| `POST /session` | Select/create one Android session by device id when no task is running. |
| `DELETE /session` | Clear active session metadata when no task is running. |
| `GET /runtime-info` | Return platform/runtime metadata, preview capability, app id presence, selected device id, and last run summary. |
| `POST /execute` | Start one dynamic goal or raw YAML-reference execution and return a request id immediately. |
| `GET /task-progress/{request_id}` | Return accumulated progress events and final result metadata for one request id. |
| `GET /screenshot` | Return a base64 screenshot and timestamp when available, or a structured unavailable/error response. |
| `GET /reports/{run_id}` | Resolve a stored Markdown or JSON report for one run id and return safe metadata or content. |

`POST /execute` accepts exactly one of `goal` or `caseYamlPath`. `goal` constructs a dynamic `Task` equivalent to CLI `--goal`. `caseYamlPath` resolves against `settings.cases.dir` first, then the current working directory, reads the complete UTF-8 file as raw text, and constructs a dynamic raw-case reference task equivalent to CLI non-strict `--case-yaml`; it must not parse YAML into strict executable steps. Playground execution should attempt post-run recording with `allow_failure=True`, matching CLI `--record --record-on-failure` behavior.

## Internal Structure

- `__init__.py`: Public exports only.
- `_server.py`: Local HTTP server, JSON route dispatch, static serving, lifecycle, and safe path handling.
- `_state.py`: In-memory session/task state, one-task lock, progress event buffering, final result summaries, and request id generation.
- `_android.py`: ADB discovery, setup schema generation, Android session metadata, and screenshot helper boundaries.
- `_execution.py`: Dynamic goal/raw-case execution adapter around `FsqAgent.run`, event capture, result/report shaping, recording, and error normalization.
- `static/`: Package-owned browser assets.
- `SPEC.md`: Module design.

## Error Handling

The playground returns JSON errors for API failures and does not expose tracebacks by default. Missing goals, missing case YAML paths, unreadable YAML references, ambiguous input bodies, ADB discovery errors, missing selected device, report resolution failures, and screenshot capture failures must produce concise structured errors. Recording failures must not change the dynamic run status.

## Design Decisions

- Goal execution follows CLI `run --goal` task construction semantics.
- YAML execution follows CLI non-strict `run --case-yaml` semantics: raw UTF-8 reference material, no strict YAML parsing for execution.
- Playground records completed dynamic runs using the post-run recorder with `allow_failure=True`.
