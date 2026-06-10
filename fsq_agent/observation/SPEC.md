# Module: observation

## Purpose

Persist run-level event timelines under the fsq-agent output directory. Screenshots, UI trees, page sources, and other runtime observations are not captured by fsq-agent itself; they are available only when configured MCP servers or tools provide those capabilities.

## Dependencies

- `models`: Uses `RunEvent`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ExecutionLogger`: Writes structured step logs, run-level trace events, and per-run live event timelines.

## Internal Structure

- `__init__.py`: Public exports only.
- `_logger.py`: Structured logging setup and event writing.
- `SPEC.md`: Module design.

## Error Handling

Event logging failures are treated as I/O errors from the underlying filesystem. Observation capture failures belong to the MCP/tool that provided the observation capability.

## Design Decisions

- fsq-agent does not implement its own screenshot or UI tree capture. Tool-specific observations should be requested through configured MCP/tools, and if a capability is not exposed by those tools then that observation type is unavailable for the run.
- Live run event timelines are persisted as `output.runs_dir/<run-id>/events.jsonl` so interrupted or long-running tasks can be inspected before final reports are generated.
- Event timelines, reports, and tool artifacts must be written under the configured output directories so installed CLI usage does not scatter artifacts across user directories.
