# Module: report

## Purpose

Generate human-readable and machine-readable reports under the fsq-agent output directory from task results, typed agent final output, execution records, normalized real tool-call events, verification outcomes, satisfied/unmet criteria, and failure diagnostics.

## Dependencies

- `models`: Uses `Task`, `AgentFinalOutput`, `ToolCallRecord`, `StepResult`, `VerificationResult`, `ReportArtifact`, and `ReportGenerationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ReportGenerator`: Generates reports for completed task runs under the configured output runs directory.
- `EvidenceBundler`: Creates a manifest for evidence references supplied by execution steps, including paths or snapshots produced by harnesses or local utility tools.
- `FailureAnalyzer`: Classifies failures as success, tool usage error, semantic action unmet, execution issue, planning issue, verification issue, or a combined label when multiple rule-assisted signals are present.
- `CoreEvidenceReportGenerator`: Generates Markdown and JSON reports from one deterministic core `evidence-manifest.json` path.

Planned execution-core report support:

- Add a report path that consumes `EvidenceBundle` records or `evidence-manifest.json` files produced by `fsq_agent.core.evidence.EvidenceRecorder`.
- Generate human-readable Markdown and machine-readable JSON summaries for deterministic core runs, including case/run identity, ordered runner step results, phase failures, event timeline summaries, artifact references, and concise failure notes.
- Keep this as a report-layer concern. `StepRunner`, `StepSequenceRunner`, `AndroidHarness`, drivers, and `EvidenceRecorder` must not know Markdown layout or report classification rules.
- The first implementation should accept an existing manifest path so device-run evidence can be reported after the run without re-executing the case.
- The existing `ReportGenerator` path for agent `StepResult` reports should remain intact until the core evidence report path is implemented and reviewed.

The first core evidence report API is:

```python
artifact = CoreEvidenceReportGenerator().generate_from_manifest(Path("runs/run-1/evidence-manifest.json"))
```

It writes `core-report.md` and `core-report.json` next to the manifest and returns `ReportArtifact(run_id=..., path=core-report.md, evidence_manifest_path=manifest_path)`.

Planned strict-regression and recovery report support:

- Regression reporting must distinguish strict testcase truth from recovery attempts. A strict run executes the YAML exactly as authored, without AI, locator fallback, or testcase mutation. A recovery run is optional and may consume strict-run failure evidence to try deterministic locator fallback or later AI-assisted repair.
- Reports should support both a single-run core evidence report and a comparison report. The single-run report summarizes one strict or recovery `evidence-manifest.json`. The comparison report combines strict evidence plus optional recovery evidence for the same testcase.
- Comparison reports should classify outcomes as `strict_passed`, `strict_failed_recovery_passed`, `strict_failed_recovery_failed`, or `strict_failed_recovery_not_attempted`.
- Recovery success must not rewrite the strict result into a normal pass. It should produce a recommendation such as updating the YAML locator, approving a deterministic fallback rule, investigating app behavior, or requiring manual review.
- Recovery attempt details should be reportable: attempted strategy, original locator/action, candidate selector or action, selected repair, result, and linked evidence artifacts.

## Internal Structure

- `__init__.py`: Public exports only.
- `_generator.py`: Markdown and JSON report generation with minimal JSON fallback, typed agent output rendering, execution/verification report shaping, and `ToolCallRecord` reconstruction from `events.jsonl`.
- `_evidence.py`: Evidence manifest and bundle creation.
- `_core_evidence_report.py`: Markdown and JSON report generation from `EvidenceBundle` or a core `evidence-manifest.json` path.
- Future `_regression_report.py`: Strict-vs-recovery comparison report generation from one strict manifest and an optional recovery manifest.
- `_failure_analysis.py`: Failure classification helpers.
- `templates/`: Optional report templates.
- `SPEC.md`: Module design.

## Error Handling

If rich Markdown/JSON report generation fails after a task run, `ReportGenerator` attempts to write `report-fallback.json` with `run_id`, `task_id`, `status`, `summary`, and the rich report error. `ReportGenerationError` is raised only when both rich report generation and minimal fallback generation fail.

## Design Decisions

- Markdown and JSON reports are part of the design because they are easy to inspect in CI and IDEs.
- JSON reports are structured by lifecycle concern: `task`, `agent_output`, `execution`, `verification`, and `failure_classification`. The `agent_output` section contains the typed `AgentFinalOutput` when available. The `execution.tool_calls` collection contains normalized `ToolCallRecord` values for real harness/local/shell tool calls reconstructed from run events; step records use `source` for runtime/provenance labels rather than overloading it as a tool name. Failure classification may use both verification output and normalized real tool-call output previews so tool usage failures can be distinguished from planning failures.
- Report artifacts are stored below `output.runs_dir/<run-id>` so installed CLI usage does not create report files in the caller's current directory.
- HTML report generation is intentionally out of scope.
- Failure analysis starts rule-assisted and can later include LLM-assisted explanations.
- Deterministic core execution reports should be generated from persisted evidence manifests rather than live runner objects. This keeps report generation replayable and allows reports to be regenerated after real-device runs.
- Regression comparison reports should be generated after execution from persisted strict and recovery manifests. This keeps self-healing auditable and prevents recovery from masking the original regression signal.
