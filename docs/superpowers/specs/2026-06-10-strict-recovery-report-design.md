# Strict Regression And Recovery Report Design

## Purpose

Regression execution must preserve the truth of the original testcase before any repair is attempted. FSQ-Agent should therefore treat strict execution and recovery execution as separate runs with separate evidence, then generate a comparison report that explains the relationship between the two.

## Execution Model

### Phase 1: Strict Regression Run

Strict run executes the YAML testcase exactly as written.

- AI is not involved.
- Locator fallback and self-healing are disabled.
- The original action order and locator payloads are preserved.
- Failures are recorded as testcase/app/device truth, not hidden by recovery.
- Evidence includes runner events, step results, screenshots, UI trees, and artifact refs.

Strict run answers one question: did the current testcase pass as authored?

### Phase 2: Recovery Run

Recovery run is optional and starts only after strict run fails.

- Recovery consumes strict-run failure evidence.
- Deterministic locator fallback may be attempted first.
- AI-assisted recovery may be added later, after deterministic recovery is auditable.
- Every recovery attempt must record the strategy, candidate selectors/actions, selected repair, and result.
- Recovery success does not rewrite the strict result.

Recovery run answers a different question: can FSQ-Agent recover enough signal to continue execution and explain the likely fix?

## Result Classification

The comparison report should use explicit final classifications:

- `strict_passed`: strict run passed; recovery was not needed.
- `strict_failed_recovery_passed`: strict run failed, recovery passed.
- `strict_failed_recovery_failed`: strict run failed, recovery also failed.
- `strict_failed_recovery_not_attempted`: strict run failed, recovery was disabled or unavailable.

AI recovery passing a case must not convert the regression result into a normal pass. It should instead produce an actionable recommendation, such as updating a YAML locator, approving a deterministic fallback rule, or investigating an app behavior change.

## Report Shape

The report layer should support two report types:

1. Single-run core evidence report: one `EvidenceBundle` or `evidence-manifest.json` becomes Markdown/JSON for a strict or recovery run.
2. Regression comparison report: strict evidence plus optional recovery evidence becomes a comparison document.

The comparison report should include:

- case identity and source path
- strict run status, failed step, primary locator, failure category, and evidence links
- recovery run status, strategy attempts, selected repair, and evidence links
- final classification
- recommendation for testcase, locator strategy, app regression, or manual review

## Ownership Boundaries

`StepRunner`, `StepSequenceRunner`, `AndroidHarness`, drivers, and `EvidenceRecorder` must not decide report layout or final regression classification.

Strict/recovery orchestration belongs in an entry or regression orchestration layer. Report rendering belongs in `fsq_agent.report`. Shared serializable result models, if needed, belong in `fsq_agent.models`.

## Implementation Order

1. Core evidence report generator for one manifest.
2. Strict run CLI/composition entry that writes strict evidence.
3. Regression comparison report for strict-only results.
4. Deterministic locator recovery mode and recovery evidence.
5. AI-assisted recovery mode after deterministic recovery is stable.
