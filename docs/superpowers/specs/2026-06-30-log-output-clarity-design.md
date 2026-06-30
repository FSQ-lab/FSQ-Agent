# Log Output Clarity Design

Date: 2026-06-30
Status: Confirmed design

## Goal

Make fsq-agent's human-facing logs easy to scan during dynamic runs. Operators should be able to tell at a glance which phase the run is in, which tool is being called, whether that call succeeded or failed, and what safe model reasoning summary or failure reason matters.

The motivating problem is that current rich streaming logs print large `tool_output_preview` values inline. Platform capability outputs can contain detailed runner JSON, artifact references, phase reports, and nested metadata. That information is useful for reports, recording, and persisted timelines, but it overwhelms terminal logs and hides the important operational story.

## Scope

This design covers only Python logging presentation for human-readable log output, especially the existing CLI rich stream rendered through `log.info`, `log.error`, and related logging calls.

The intended implementation changes are limited to CLI log rendering helpers and focused tests. The primary implementation surface is `fsq_agent/cli/_formatting.py`; `fsq_agent/cli/_logging.py` may remain a thin base formatter unless the later SPEC phase identifies a small formatting need there.

## Non-Goals

This design does not change dynamic execution flow, pre-planning, main execution, verification, strict replay, recording, report generation, or playground behavior.

This design does not change `RunEvent`, `events.jsonl`, report JSON/Markdown, recording manifests, generated strict YAML, tool artifacts, or any intermediate file content.

This design does not add YAML configuration, CLI flags, or public APIs.

This design does not remove detailed tool output from persisted data. Detailed output should remain available through existing run artifacts, reports, and event timelines.

This design does not expose hidden model chain-of-thought. It may display only safe reasoning summaries already surfaced by the SDK/runtime as `reasoning_summary` events or existing safe messages.

## Proposed Design

### Approach Selected

Use formatter-only log cleanup.

The CLI rich stream should render concise, phase-tagged operational summaries from existing `RunEvent` data. It should not require runtime event schema changes or persisted payload changes. `--stream-format jsonl` should continue to emit the raw serialized `RunEvent` without prefixes or display compaction so machine consumers remain compatible.

### Alternatives Considered

#### Approach A: Formatter-Only Cleanup

Derive display phase, status, tool name, failure category, artifact hints, and short detail text from existing event fields and payloads inside CLI formatting helpers.

Trade-off: This is the smallest compatible change. It improves the user-visible logs without changing execution data or report inputs. This is the selected approach.

#### Approach B: Event Payload Fields plus Formatter

Add explicit display-stage or display-summary fields to `RunEvent.payload` and update the CLI formatter to consume them.

Trade-off: This could make display semantics more explicit, but it changes persisted event data and may ripple into report, recording, playground, or future tooling. That exceeds the confirmed scope.

#### Approach C: Full Observability Redesign

Redesign event schemas, reports, playground views, and terminal logs together.

Trade-off: This may be useful later, but it is intentionally out of scope for a focused log-output improvement.

## Public Behavior

Human-readable rich logs should become phase-oriented and concise. A dynamic run should read as a timeline of phase transitions and tool outcomes rather than a stream of nested JSON.

Each rich log entry should prioritize:

- phase label,
- event sequence,
- event status,
- tool name when present,
- concise arguments when useful,
- duration when known,
- safe reason or error summary when relevant,
- artifact/report hint when detailed output is available elsewhere.

Representative target shape:

```text
[PRE-PLAN #7] completed: Goal pre-plan injected - 5 key actions, verification goal ready
[EXECUTION #12] tool started: tap_on args={"target":"Downloads"}
[EXECUTION #13] tool passed: tap_on duration=842ms artifacts=screenshot,page_snapshot
[EXECUTION #18] model reason: Need to verify the downloads panel is visible before final answer.
[VERIFICATION #25] completed: Verification task completed - success
```

Exact wording can be adjusted during implementation, but the logs must keep the same core information visible: phase, tool, success or failure, duration, and safe reason/error summary.

## Log Rendering Rules

The rich formatter should derive a display phase from existing event data:

- `PRE-PLAN` for pre-plan events such as `Pre-plan started`, knowledge-page planning tool calls, and `Goal pre-plan injected`.
- `STARTUP` for provider, harness, tool setup, and SDK agent readiness events.
- `EXECUTION` for main planning, model messages, reasoning summaries, and real AgentTool/CommonTool/PlatformTool calls.
- `VERIFICATION` for verification-task startup, verification reasoning summaries, verification completion, and verification failures when identifiable from existing titles/messages.
- `REPORT` for report path/result logging if routed through the same formatting surface.
- `RUN` as the fallback for run started, run completed, run failed, or unclassified events.

The formatter should derive tool outcome from existing fields in this order:

1. `event.payload["status"]` when present.
2. `event.payload["runner_result"]["status"]` when present and safe to read.
3. `event.type`, using completed/failed/start semantics as fallback.

The formatter should derive tool identity from:

1. `event.tool_name`.
2. `event.payload["tool_name"]`.
3. `event.payload["capability_name"]`.
4. `unknown` only when no safe name exists.

Arguments should be shown only through the existing redacted `event.tool_arguments` value and should remain compact. Multi-line or long argument payloads should be flattened and truncated.

Large tool outputs should not be printed inline by default. For `tool_call_completed`, the formatter should summarize known safe fields such as status, failure category, error message, duration, and artifact refs. It should omit verbose JSON output previews unless the output is short and no better summary exists.

When verbose output is omitted, the log should say where to look when possible, using existing `payload.artifact_path`, `payload.artifact_refs`, report path, or generic run artifacts wording. It should not invent new files or artifact records.

Failures should remain explicit. For `tool_call_failed`, `run_failed`, and completed tool calls whose payload status is failed, logs should include the error message and failure category when available, even if the output preview is otherwise suppressed.

`reasoning_summary` events should remain visible as safe model reason summaries. They should be phase-tagged and truncated to a readable single-line summary. The formatter must not label these as hidden chain-of-thought.

`jsonl` stream format must bypass all rich display behavior and keep emitting one raw serialized event per log message.

## Module Ownership

`cli` owns this change because CLI already owns stream rendering and terminal output. The change belongs in private CLI formatting helpers rather than in the agent runtime.

`agent` should not change for this iteration. It already emits safe structured events with tool names, arguments, output previews, payload metadata, and reasoning-summary messages.

`models` should not change because the existing `RunEvent` contract already contains enough data for display derivation.

`report`, `observation`, and `playground` should not change in this iteration because the confirmed scope excludes intermediate artifacts and other views.

## Python Architecture

Architecture level: Level 3 Layered Application for the affected `cli` module.

Public API: unchanged. The public CLI commands remain `init`, `run`, `report`, and `playground`; no new options are introduced.

Internal modules: private helpers in `fsq_agent/cli/_formatting.py` may be added or adjusted. These helpers should remain internal to the CLI module.

Domain boundaries: runtime orchestration remains in `agent`; persisted event writing remains in `observation`; report rendering remains in `report`; CLI owns only argument handling and human-facing output rendering.

Boundary models: existing `RunEvent` and `TaskResult` models from `models` remain the boundary data. No new Pydantic model is required for this iteration.

Dependency direction: `cli` may consume `models.RunEvent`; lower-level modules must not import CLI formatting helpers.

Rationale: The existing CLI module is already a layered application boundary coordinating user-facing command behavior. A small internal formatter is sufficient; a new observability package, service layer, or event schema is not justified.

## Edge Cases

If a tool completion event has no parseable payload and only a short preview, the formatter may show that preview because it is the only available diagnostic detail.

If a tool completion event has no parseable payload and a long preview, the formatter should truncate aggressively and mark the detail as omitted or previewed.

If `tool_call_completed` lacks a `tool_name`, the formatter may pair only what the event already provides. It must not infer tool names from previous process-global state unless a simple local formatter helper can do so without mutating persisted data or changing event emission.

If a failure is represented as a completed tool call with `status="failed"` in payload, the rich log should render it as a failed tool outcome even though the event type is `tool_call_completed`.

If output contains secret redaction markers or sensitive payload shapes already handled by runtime redaction, the formatter should not attempt to reverse or expand them.

## Affected Specs Expected To Change

- `fsq_agent/cli/SPEC.md`: document concise phase-tagged rich log rendering, verbose output suppression in human logs, preserved JSONL/raw event behavior, and unchanged public CLI flags.

No root `SPEC.md`, `agent/SPEC.md`, `models/SPEC.md`, `observation/SPEC.md`, or `report/SPEC.md` changes are expected unless the spec-driven phase finds an existing contradiction.

## Verification Expectations

Focused tests should cover the CLI formatting behavior with constructed `RunEvent` values:

- pre-plan, startup, execution, verification, and run-level events render with clear phase labels,
- tool started logs include tool name and compact redacted arguments,
- successful tool completed logs include status, tool name, duration, and artifact hints without dumping large JSON,
- failed tool completed or failed tool events include failure category and error message,
- `reasoning_summary` logs preserve a safe single-line model reason summary,
- long `tool_output_preview` content is omitted or tightly truncated in rich logs,
- `stream_format="jsonl"` still writes the raw event JSON without rich prefixes or display compaction.

Expected focused verification command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cli.py
```

If implementation adds a dedicated formatting test file, include that file in the focused command. A full test-suite run remains appropriate before completion if the later implementation touches shared CLI behavior more broadly than expected.

## Open Questions Resolved

- Log surface: optimize only `log.debug/info/error/...` style human logs, not `events.jsonl`, reports, recording, artifacts, or other intermediate outputs.
- Approach: use formatter-only cleanup.
- Configuration: do not add YAML settings or CLI flags.
- Event schema: do not change `RunEvent` or persisted event payloads.
- Reasoning visibility: show only safe existing reasoning summary messages; do not expose hidden chain-of-thought.

## Handoff

Next step: translate this confirmed design into `fsq_agent/cli/SPEC.md` updates using the spec-driven workflow. Implementation must wait until those SPEC updates are confirmed.