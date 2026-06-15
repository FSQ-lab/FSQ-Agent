# Module: report

## Purpose

Generate human-readable and machine-readable reports under the fsq-agent output directory from dynamic LLM task results and strict-core evidence manifests, including the checked dynamic `verification_goal`, CommonTool/harness tool provenance, and provider-backed AI assertion verdict metadata. Provide one lookup path so CLI can print a stored LLM or strict-core report by run id.

## Dependencies

- `models`: Uses `Task`, `AgentFinalOutput`, `ToolCallRecord`, `StepResult`, `VerificationResult`, `ReportArtifact`, `EvidenceBundle`, `AIAssertionResult`, and `ReportGenerationError`.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `ReportGenerator`: Generates reports for completed task runs under the configured output runs directory.
- `EvidenceBundler`: Creates a manifest for evidence references supplied by execution steps, including paths or snapshots produced by harnesses or CommonTool utilities.
- `FailureAnalyzer`: Classifies failures as success, tool usage error, semantic action unmet, execution issue, planning issue, verification issue, or a combined label when multiple rule-assisted signals are present.
- `CoreEvidenceReportGenerator`: Generates Markdown and JSON reports from one deterministic core `evidence-manifest.json` path.
- `resolve_report_path(runs_dir: Path, run_id: str, report_format: Literal["markdown", "json"] = "markdown") -> Path`: Resolves a stored LLM report (`report.md/json`) or strict-core report (`core-report.md/json`) for the requested run id. It returns exactly one matching path or raises `ReportGenerationError` when the report is missing or ambiguous.

The core evidence report API is:

```python
artifact = CoreEvidenceReportGenerator().generate_from_manifest(Path("runs/run-1/evidence-manifest.json"))
```

It writes `core-report.md` and `core-report.json` next to the manifest and returns `ReportArtifact(run_id=..., path=core-report.md, evidence_manifest_path=manifest_path)`.

Planned strict-regression and recovery report support:

- Regression reporting must distinguish strict testcase truth from recovery attempts. A strict run executes the YAML exactly as authored, without locator fallback, testcase mutation, or AI recovery. Explicit authored `assertWithAI` verdicts are assertion evidence within the strict run, not recovery. A recovery run is optional and may consume strict-run failure evidence to try deterministic locator fallback or later AI-assisted repair.
- Reports should support both a single-run core evidence report and a comparison report. The single-run report summarizes one strict or recovery `evidence-manifest.json`. The comparison report combines strict evidence plus optional recovery evidence for the same testcase.
- Comparison reports should classify outcomes as `strict_passed`, `strict_failed_recovery_passed`, `strict_failed_recovery_failed`, or `strict_failed_recovery_not_attempted`.
- Recovery success must not rewrite the strict result into a normal pass. It should produce a recommendation such as updating the YAML locator, approving a deterministic fallback rule, investigating app behavior, or requiring manual review.
- Recovery attempt details should be reportable: attempted strategy, original locator/action, candidate selector or action, selected repair, result, and linked evidence artifacts.

## Internal Structure

- `__init__.py`: Public exports only.
- `_generator.py`: Markdown and JSON report generation with minimal JSON fallback, typed agent output rendering, execution/verification report shaping, and `ToolCallRecord` reconstruction from `events.jsonl`.
- `_evidence.py`: Evidence manifest and bundle creation.
- `_core_evidence_report.py`: Markdown and JSON report generation from `EvidenceBundle` or a core `evidence-manifest.json` path.
- `_resolver.py`: Stored report lookup for LLM `report.*` and strict-core `core-report.*` files.
- Future `_regression_report.py`: Strict-vs-recovery comparison report generation from one strict manifest and an optional recovery manifest.
- `_failure_analysis.py`: Failure classification helpers.
- `templates/`: Optional report templates.
- `SPEC.md`: Module design.

## Error Handling

If rich Markdown/JSON report generation fails after a task run, `ReportGenerator` attempts to write `report-fallback.json` with `run_id`, `task_id`, `status`, `summary`, and the rich report error. `ReportGenerationError` is raised only when both rich report generation and minimal fallback generation fail.

Stored report lookup raises `ReportGenerationError` when no report exists for the requested run id/format or when both LLM and strict-core report files exist for the same run id/format.

## Design Decisions

- Markdown and JSON reports are part of the design because they are easy to inspect in CI and IDEs.
- JSON reports are structured by lifecycle concern: `task`, `agent_output`, `execution`, `verification`, and `failure_classification`. The `task` and `verification` sections should make the single checked dynamic `verification_goal` visible for LLM runs. The `agent_output` section contains the typed `AgentFinalOutput` when available. The `execution.tool_calls` collection contains normalized `ToolCallRecord` values for real harness and CommonTool calls reconstructed from run events; tool origins are `harness`, `common`, `runtime`, or `unknown`. Runtime-only records such as progress events, pre-plan reconstruction, provider setup, and SDK runner summaries are not represented as real tool calls. Step records use `source` for runtime/provenance labels rather than overloading it as a tool name. Failure classification may use both verification output and normalized real tool-call output previews so tool usage failures can be distinguished from planning failures.
- Reports must preserve AI assertion evidence emitted by harness actions. For Android `assertWithAI`, reports should include the prompt summary, verdict status, explanation, provider/model metadata safe for display, latency/token diagnostics when safe, screenshot artifact references, and any evaluator error. Reports must not re-inspect screenshot pixels or include hidden model reasoning.
- Report artifacts are stored below `output.runs_dir/<run-id>` so installed CLI usage does not create report files in the caller's current directory.
- LLM and strict-core reports intentionally keep separate internal shapes. CLI unifies only lookup and printing through `resolve_report_path`.
- HTML report generation is intentionally out of scope.
- Failure analysis starts rule-assisted and can later include LLM-assisted explanations.
- Deterministic core execution reports should be generated from persisted evidence manifests rather than live runner objects. This keeps report generation replayable and allows reports to be regenerated after real-device runs.
- Regression comparison reports should be generated after execution from persisted strict and recovery manifests. This keeps self-healing auditable and prevents recovery from masking the original regression signal. AI assertion verdicts in strict evidence remain part of the strict result, while AI-assisted repair attempts belong only to separate recovery evidence.
