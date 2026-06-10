# Module: report

## Purpose

Generate human-readable and machine-readable reports under the fsq-agent output directory from task results, typed agent final output, execution records, normalized real tool-call events, verification outcomes, satisfied/unmet criteria, and failure diagnostics.

## Dependencies

- `models`: Uses `Task`, `AgentFinalOutput`, `ToolCallRecord`, `StepResult`, `VerificationResult`, `ReportArtifact`, and `ReportGenerationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ReportGenerator`: Generates reports for completed task runs under the configured output runs directory.
- `EvidenceBundler`: Creates a manifest for evidence references supplied by execution steps, including paths or snapshots produced by configured MCP/tools.
- `FailureAnalyzer`: Classifies failures as success, tool usage error, semantic action unmet, execution issue, planning issue, verification issue, or a combined label when multiple rule-assisted signals are present.

## Internal Structure

- `__init__.py`: Public exports only.
- `_generator.py`: Markdown and JSON report generation with minimal JSON fallback, typed agent output rendering, execution/verification report shaping, and `ToolCallRecord` reconstruction from `events.jsonl`.
- `_evidence.py`: Evidence manifest and bundle creation.
- `_failure_analysis.py`: Failure classification helpers.
- `templates/`: Optional report templates.
- `SPEC.md`: Module design.

## Error Handling

If rich Markdown/JSON report generation fails after a task run, `ReportGenerator` attempts to write `report-fallback.json` with `run_id`, `task_id`, `status`, `summary`, and the rich report error. `ReportGenerationError` is raised only when both rich report generation and minimal fallback generation fail.

## Design Decisions

- Markdown and JSON reports are part of the design because they are easy to inspect in CI and IDEs.
- JSON reports are structured by lifecycle concern: `task`, `agent_output`, `execution`, `verification`, and `failure_classification`. The `agent_output` section contains the typed `AgentFinalOutput` when available. The `execution.tool_calls` collection contains normalized `ToolCallRecord` values for real MCP/local/hosted/shell tool calls reconstructed from run events; step records use `source` for runtime/provenance labels rather than overloading it as a tool name. Failure classification may use both verification output and normalized real tool-call output previews so tool usage failures can be distinguished from planning failures.
- Report artifacts are stored below `output.runs_dir/<run-id>` so installed CLI usage does not create report files in the caller's current directory.
- HTML report generation is intentionally out of scope.
- Failure analysis starts rule-assisted and can later include LLM-assisted explanations.
