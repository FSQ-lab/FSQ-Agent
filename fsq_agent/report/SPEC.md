# Module: report

## Purpose

Generate human-readable and machine-readable reports under the fsq-agent output directory from task results, plan summaries, execution records, tool-call events, verification outcomes, satisfied/unmet criteria, and failure diagnostics.

## Dependencies

- `models`: Uses `Task`, `StepResult`, `VerificationResult`, `TaskResult`, `ReportArtifact`, and `ReportGenerationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ReportGenerator`: Generates reports for completed task runs under the configured output runs directory.
- `EvidenceBundler`: Creates a manifest and optional archive containing screenshots, UI trees, logs, and traces.
- `FailureAnalyzer`: Classifies failures as planning issue, execution issue, environment issue, verification issue, or unknown.

## Internal Structure

- `__init__.py`: Public exports only.
- `_generator.py`: Markdown and JSON report generation with minimal JSON fallback, plan/execution/verification report shaping, and tool-call event summarization from `events.jsonl`.
- `_evidence.py`: Evidence manifest and bundle creation.
- `_failure_analysis.py`: Failure classification helpers.
- `templates/`: Optional report templates.
- `SPEC.md`: Module design.

## Error Handling

If rich Markdown/JSON report generation fails after a task run, `ReportGenerator` attempts to write `report-fallback.json` with `run_id`, `task_id`, `status`, `summary`, and the rich report error. `ReportGenerationError` is raised only when both rich report generation and minimal fallback generation fail.

## Design Decisions

- Markdown and JSON reports are part of the design because they are easy to inspect in CI and IDEs.
- JSON reports are structured by lifecycle concern: `task`, `plan`, `execution`, `verification`, and `failure_classification`. The `execution.tool_calls` collection contains real MCP/local tool calls reconstructed from run events; step records use `source` for runtime/provenance labels rather than overloading it as a tool name.
- Report artifacts are stored below `output.runs_dir/<run-id>` so installed CLI usage does not create report files in the caller's current directory.
- HTML report generation is intentionally out of scope.
- Failure analysis starts rule-assisted and can later include LLM-assisted explanations.
