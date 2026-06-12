# Raw Case Planning Reference Design

## Goal

Dynamic `fsq-agent run --case-yaml` and `--case-dir` executions should give the pre-plan stage the complete raw case reference before UI execution begins. The pre-plan stage must read the authored raw YAML content and combine it with page knowledge to generate an ordered key-action flow. The generated key actions become the execution spine for the main dynamic agent, while the main agent remains free to adapt during execution based on live UI state, transient dialogs, existing app state, and recoverable tool failures.

The immediate problem is that raw case tasks currently carry the full YAML in `Task.description`, but pre-plan selection prefers the final `verification_goal`. For raw case tasks that goal only says to execute the referenced file name, so the pre-planner may infer a flow from page knowledge rather than honoring the authored YAML content.

## Scope

In scope:

- Add a clear planning-reference contract to dynamic `Task` data so pre-plan input is not conflated with final verification text.
- Populate that planning reference from complete raw YAML content for `--case-yaml` and each file in `--case-dir`.
- Keep natural-language `--goal` planning behavior intact by using the normalized goal as the planning reference.
- Update agent pre-plan input selection to prefer the explicit planning reference and fall back to the existing goal/description behavior only for compatibility.
- Update pre-plan instructions and input shape so raw case content is primary and page knowledge is auxiliary.
- Preserve dynamic execution semantics: generated key actions guide execution order, but the main agent may still adapt using fresh runtime evidence.
- Add verification coverage for raw YAML fidelity, goal-task regression, and warning behavior.

Out of scope:

- Converting dynamic `--case-yaml` into strict replay.
- Parsing YAML into local `ExecutableStep` records for dynamic execution.
- Changing final verification mode semantics.
- Changing dynamic recording eligibility or replay-command reconstruction.
- Adding raw-reference summarization or truncation. If planning-reference size becomes a problem, a later design should handle summarization explicitly because truncation can damage authored-flow fidelity.
- Runtime setup observability, artifact path propagation, and Android connection timeout behavior. Those belong in a separate observability design.

## Proposed Design

### Planning Reference Contract

Add explicit planning-reference fields to the shared dynamic task contract:

- `planning_reference_text`: the authoritative text the pre-planner should use to derive ordered key actions.
- `planning_reference_kind`: the kind of reference, initially `goal` or `raw_case`.

Both fields are optional for compatibility, but first-party CLI task construction should populate both for all dynamic entry paths.

The planning reference is not final verification text and is not a parsed execution plan.

Expected values:

- `--goal`: `planning_reference_kind="goal"`; `planning_reference_text` is the normalized natural-language goal.
- `--case-yaml`: `planning_reference_kind="raw_case"`; `planning_reference_text` is source path plus the complete raw YAML text.
- `--case-dir`: each discovered case receives `planning_reference_kind="raw_case"` and its own source path plus complete raw YAML text.
- External callers: may omit the fields and rely on compatibility fallback, or supply their own task/reference text.

The final verification fields remain separate. `verification_goal` and `verification_criteria` decide what the verifier judges at the end; they must not be the first choice for pre-plan input.

### CLI Task Construction

The CLI continues to read raw case files as UTF-8 text and must not parse, normalize, or convert them into local steps for dynamic execution.

For raw case tasks, CLI should set:

- `description`: human/model-facing task context that includes source path and raw content as today.
- `planning_reference_kind`: `raw_case`.
- `planning_reference_text`: source path and complete raw case content in a stable envelope.
- `verification_goal` and `verification_criteria`: goal-level final success criteria, unchanged in meaning.

For goal tasks, CLI should set `planning_reference_kind` to `goal` and `planning_reference_text` to the normalized goal string. This keeps the current goal-driven pre-plan behavior but makes it explicit.

### Agent Pre-plan Input Selection

Replace the current pre-plan goal selection behavior with a helper that prefers the explicit planning reference:

1. If `task.planning_reference_text` is non-empty, use it.
2. If `task.planning_reference_kind` is set, pass it through as `reference_type`; otherwise pass a compatibility value such as `unknown` or infer `goal` only for first-party goal tasks.
3. Otherwise, fall back to existing behavior for compatibility with older tests and external callers.

This change specifically prevents raw case pre-plan from using the generic `verification_goal` that only contains the file name.

### Pre-plan Input Shape and Instructions

The pre-plan model input should distinguish reference type from reference text. A concrete shape can include:

- `reference_type`: the task planning reference kind, initially `goal`, `raw_case`, or compatibility `unknown`.
- `reference_text`: the planning reference.
- `knowledge_items`: existing page-knowledge index and pages loaded through runtime tools.
- `skills`: loaded automation guidance.
- `output_schema`: unchanged `GoalPrePlan` schema unless SPEC review decides a source-trace field is needed.

Prompt behavior for raw case references:

- First extract the authored ordered flow from the raw YAML/text.
- Preserve authored action/assertion order for business-relevant steps.
- Treat `launchApp` and `killApp` as setup/teardown intent rather than ordinary business key actions unless they are semantically central to the case.
- Use page knowledge to enrich action wording, page transitions, locator hints, and recovery context.
- Do not replace raw YAML steps with knowledge-derived alternatives when the two disagree.
- If page knowledge is incomplete or mismatched, keep the raw flow and add warnings.

### Main Execution Semantics

Generated key actions continue to be execution guidance, not strict-core executable steps. The main dynamic agent should:

- Preserve relative order of generated key actions.
- Execute the authored case intent represented by those key actions.
- Insert setup, dialog handling, fresh observations, waits, or recovery as needed based on live UI state.
- Verify important state transitions with fresh harness evidence rather than historical artifact search alone.

Dynamic recording remains event-driven. It must continue to reconstruct replayable commands only from actual run events, not from pre-plan output.

## Affected Specs Expected To Change

- Root `SPEC.md`: module table likely unchanged, but design decisions may need a short note that dynamic raw case planning uses an explicit planning reference.
- `fsq_agent/models/SPEC.md`: add the `Task.planning_reference_kind` and `Task.planning_reference_text` contracts and clarify separation from verification fields.
- `fsq_agent/cli/SPEC.md`: state that dynamic `--case-yaml` and `--case-dir` populate planning reference with complete raw file content while still not parsing YAML for execution.
- `fsq_agent/agent/SPEC.md`: update pre-plan input selection, raw-reference priority rules, and knowledge-as-auxiliary behavior.
- Tests may need updates, but test files are not specification sources.

## Error Handling and Edge Cases

- Invalid YAML remains acceptable for dynamic raw case execution because the dynamic path treats the file as raw text reference. The pre-planner should attempt to infer intent from text. If it cannot form a useful key-action chain, it should return an empty plan and warnings rather than causing CLI input validation failure.
- Planning reference should not be silently truncated. Any future summarization or size limit must preserve authored flow and should be designed separately.
- If the raw reference contains steps not found in page knowledge, the pre-plan should keep those steps and warn about missing knowledge coverage.
- If page knowledge suggests a different route or item set than the raw reference, the raw reference wins and the mismatch should appear in warnings.
- Runtime secret values must not be written into events, reports, generated YAML, or artifacts. If a raw reference contains a runtime-secret reference by environment variable name, only the name may appear.
- Existing external callers that do not set planning-reference fields should continue using fallback behavior.

## Verification Expectations

Implementation should include focused tests for these behaviors:

- CLI raw case task construction includes `planning_reference_kind="raw_case"` and the complete raw YAML in the planning reference.
- Agent pre-plan input selection prefers planning reference over `verification_goal`.
- The representative settings case pre-plan can include the `Microsoft services` flow from raw YAML rather than only the inferred first four settings items from page knowledge.
- Goal tasks continue to use the natural-language goal as planning reference.
- Pre-plan warnings can represent raw-reference and page-knowledge gaps or mismatches without changing the authored flow.
- Dynamic recording still ignores pre-plan output when generating replayable strict cases and uses only actual run events.

## Resolved Questions

- The selected approach is to add an explicit planning-reference contract instead of relying on `Task.description` shape or adding a separate case-summary model call.
- The pre-plan must read the whole YAML content for raw case tasks.
- Page knowledge should enrich and ground the authored flow, not replace it.
- Execution remains dynamic after pre-plan; the main agent may adapt to live UI state while preserving the planned flow's relative order.

## Handoff

After this design is approved, use the `spec-driven` workflow to update root/module `SPEC.md` files before implementation. Implementation must follow the confirmed SPEC updates, not this design document alone.
