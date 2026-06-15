# LLM Execution Goal Verification Design

## Goal

Redesign the dynamic LLM execution chain so final verification is simple, goal-based, and aligned with how dynamic runs actually work today. The dynamic LLM path should no longer expose or implement configurable verification modes. Instead, pre-plan becomes the single input-understanding stage that converts either a user `--goal` string or raw YAML case text into:

- `key_actions`: structured ordered actions used by the main LLM execution stage.
- `verification_goal`: one string used by the final evidence-based verifier.

The intended chain is:

```text
--goal text or raw YAML case text
  -> pre-plan
      -> key_actions
      -> verification_goal
  -> main LLM execution loop
  -> final verifier checks verification_goal against execution evidence
  -> optional dynamic recording reconstructs replay YAML from actual events only
```

## Scope

In scope:

- Dynamic LLM `fsq-agent run --goal` execution.
- Dynamic LLM `fsq-agent run --case-yaml` and `--case-dir` execution.
- Removing `verification.mode` from public configuration and dynamic runtime behavior.
- Removing `normal`, `strict`, and `goal` verification-mode branching and the related code paths.
- Extending pre-plan output to include both `key_actions` and `verification_goal`.
- Making raw YAML case steps advisory only for dynamic LLM execution.
- Updating prompt, verifier, report, README/config examples, and tests after SPEC confirmation.

Out of scope:

- Strict-core `fsq-agent run --strict` execution. Strict-core continues to parse YAML into deterministic `ExecutableStep` values and produce core evidence reports.
- Parsing raw YAML steps into local deterministic dynamic execution steps.
- Adding a separate LLM summarizer before pre-plan.
- Changing dynamic recording eligibility or replay-command reconstruction.
- Adding replacement assertion/operation verification modes under different names.

## Current Behavior Summary

The public dynamic CLI path already behaves close to goal-only verification. `--goal` creates a goal-level task, and raw `--case-yaml` reads the complete case file as UTF-8 text rather than parsing YAML commands. The CLI does not derive `assertion` or `operation` verification criteria from raw YAML steps.

The current code still exposes a larger verification surface:

- `verification.mode` in config, with `normal`, `strict`, and `goal` values.
- `VerificationMode` in models.
- `VerificationCriterion.kind`, with `goal`, `assertion`, and `operation` values.
- `Task.blocking_verification_criteria(mode)`.
- Verifier and verification evidence paths that apply mode filtering.

This creates a mismatch: users can configure verification modes that do not meaningfully change first-party dynamic CLI behavior because dynamic raw YAML does not produce structured assertion/operation criteria. The redesign removes that misleading surface and makes goal-only verification explicit.

## Proposed Design

### 1. Single Dynamic Verification Strategy

Dynamic LLM final verification should always validate one goal string:

```python
verification_goal: str | None = None
```

The final verifier should answer one question: does the supplied execution evidence prove the `verification_goal`?

Final status rules:

- `success`: evidence supports the verification goal.
- `failed`: evidence proves the verification goal is unmet or cannot be completed.
- `inconclusive`: evidence is insufficient or ambiguous and does not prove either success or failure.

There is no user-configurable verification strictness for dynamic LLM runs.

### 2. Pre-Plan Output Contract

`GoalPrePlan` should include a required verification-goal field alongside key actions:

```python
class GoalPrePlan(BaseModel):
    goal: str
    key_actions: list[GoalKeyAction]
    verification_goal: str
    relevant_page_ids: list[str]
    summary: str
    warnings: list[str]
```

`key_actions` are for execution. They describe the ordered action spine that the main LLM loop should follow while still adapting to live UI state, dialogs, setup, waits, and recovery.

`verification_goal` is for final verification. It summarizes the user-visible outcome that evidence must prove after the main execution loop completes.

`summary` remains human-facing explanatory text and must not be used as the verification contract.

### 3. Goal Input Behavior

For `fsq-agent run --goal TEXT`:

- CLI normalizes the user text and stores it as `planning_reference_text` with `planning_reference_kind="goal"`.
- Pre-plan reads the normalized user goal and page knowledge.
- Pre-plan emits ordered `key_actions` for execution.
- Pre-plan emits `verification_goal` as a concise summary of what the user asked to prove.
- Main execution receives both the key actions and verification goal.
- Final verifier checks only `verification_goal` against execution evidence.

The raw user text should not be treated as the final verifier contract without pre-plan. Pre-plan is responsible for producing the stable structured `verification_goal` string.

### 4. Raw YAML Case Behavior

For dynamic `fsq-agent run --case-yaml` and `--case-dir`:

- CLI continues to read each `.codex.yaml` file as complete UTF-8 text.
- CLI does not call the FSQ YAML loader for dynamic execution.
- CLI does not parse YAML steps into local execution steps.
- CLI does not extract assertion/operation verification criteria from YAML steps.
- CLI passes the raw text to pre-plan as `planning_reference_kind="raw_case"`.
- Pre-plan treats the raw case text as source material for understanding case intent.

Raw YAML steps are advisory only in dynamic LLM execution. They may help pre-plan infer an ordered action flow, but they are not assumed to be fully accurate, complete, current, or reliable. They must not become final verification criteria by simple transformation.

For `verification_goal`, pre-plan should prefer case-level intent signals in the raw text, such as case name, description-like fields, metadata, tags, properties, and other human-authored goal text when present. Step content may be used only as supporting context when case-level intent is incomplete or ambiguous.

This does not require local YAML parsing. The raw text is model input. The model may recognize YAML-like fields as text, but the runtime does not convert YAML documents into structured FSQ models on the dynamic path.

### 5. Pre-Plan Instruction Constraints

Pre-plan instructions must be explicit and conservative.

For `key_actions`:

- Generate an ordered execution spine from the user goal or raw case intent.
- Use raw YAML steps as a reference path, not as a brittle script.
- Use page knowledge for grounding page names, elements, transitions, and locator hints.
- Preserve the likely user-visible flow, but allow the main execution loop to adapt to live UI state.

For `verification_goal`:

- Generate exactly one concise string.
- Derive it from the user's `--goal` text or the raw case's case-level intent.
- Do not freely expand the goal into broader test coverage.
- Do not turn intermediate operations into final verification requirements.
- Do not add unrelated product, account, network, performance, visual-regression, or accessibility checks unless explicitly requested by the input.
- Treat YAML steps as supporting evidence only; if steps conflict with case-level intent, case-level intent wins and the conflict should be recorded in `warnings`.
- If input facts are insufficient to summarize a reliable verification goal, return an empty `verification_goal` and warnings rather than inventing a goal.

Examples of good `verification_goal` values:

```text
Verify that the user can open Downloads from the browser overflow menu and return to the New Tab Page.
Verify that each explicitly targeted first-level Settings item can be opened from the Settings page.
Verify that the user can open a new InPrivate tab from the overflow menu and reach the expected InPrivate tab state.
```

Examples of bad `verification_goal` values:

```text
Verify all Settings items work.
Verify no visual regressions exist.
Verify every intermediate tap from the YAML succeeded.
Verify performance and accessibility are acceptable.
Execute the referenced case content from verify_settings.codex.yaml.
```

### 6. Agent Orchestration

`FsqAgent.run` should ensure pre-plan-derived execution and verification context exists before external UI actions begin.

Expected dynamic flow:

1. CLI builds a `Task` with planning reference kind/text and no final file-name-only verification criterion.
2. `FsqAgent.run` loads knowledge and skills.
3. `FsqAgent.run` runs pre-plan with the explicit planning reference.
4. The returned key actions are copied into `Task.key_actions`.
5. The returned verification goal is copied into `Task.verification_goal`.
6. If pre-plan does not produce a usable verification goal, the run fails before external UI action.
7. If pre-plan does not produce useful key actions, the run fails before external UI action.
8. The main LLM loop executes using key actions as the ordered spine.
9. The evidence-based verifier checks only `Task.verification_goal`.

Generated key actions should not become additional blocking verifier requirements. They remain execution guidance and report diagnostics.

### 7. Verifier Contract

The verifier should no longer accept or apply a verification mode.

Verifier input should include:

- `verification_goal`: the single final target.
- `execution_steps`: execution records and runner/verifier summaries.
- `tool_calls`: normalized harness/CommonTool calls reconstructed from events.
- `artifacts`: bounded evidence excerpts.
- `agent_claims`: main agent claims, treated as claims rather than proof.

Verifier instructions should say:

- Use only supplied evidence.
- Check the single `verification_goal`.
- Do not infer extra goals from key actions.
- Do not transform key actions into independent final criteria.
- Return `inconclusive` when evidence is insufficient.
- Preserve explicit harness-owned AI assertion evidence when it exists, but do not add visual checks that were not requested by the verification goal.

### 8. Configuration and Compatibility

Remove `verification.mode` from public configuration and examples.

Remove or simplify:

- `VerificationSettings`.
- `VerificationMode`.
- `VerificationCriterionKind` and mode-specific blocking logic.
- `Task.blocking_verification_criteria(mode)`.
- Prompt text that says verification mode is applied later.
- Verifier evidence fields that partition blocking/nonblocking criteria by mode.

Existing config files that still contain `verification.mode` should fail validation after implementation. This avoids silently ignoring an obsolete setting that users may expect to change runtime behavior.

If later external APIs need multiple verification goals or typed criteria, that should be designed separately. This design intentionally keeps the first-party dynamic LLM path to one `verification_goal` string.

### 9. Strict-Core Boundary

This design does not change strict-core execution.

`fsq-agent run --strict` continues to:

- Parse `.codex.yaml` files through `fsq`.
- Convert commands to deterministic `ExecutableStep` records.
- Resolve strict replay refs before UI actions.
- Execute through `StepSequenceRunner` and harnesses.
- Generate `evidence-manifest.json` and `core-report.md/json`.
- Avoid LLM pre-plan and final verifier mode behavior, except for explicitly authored `assertWithAI` evaluator calls when configured.

## Public Behavior

After implementation:

- Users no longer configure `verification.mode`.
- Dynamic `--goal` runs use pre-plan-generated key actions and verification goal.
- Dynamic raw YAML runs use pre-plan-generated key actions and verification goal derived from raw case intent.
- Raw YAML steps can influence execution planning but are not trusted as exact verification truth.
- Final verification checks one goal string.
- Reports show the verification goal that was checked.
- Key actions remain visible as execution guidance and diagnostics.
- Dynamic recording remains event-based and does not record pre-plan guesses as replay commands.

## Error Handling and Edge Cases

- Empty `--goal` remains an input validation failure.
- A pre-plan result with no usable `verification_goal` fails before external UI actions.
- A pre-plan result with no useful key actions fails before external UI actions.
- Invalid YAML remains acceptable for dynamic raw case execution if the file is valid UTF-8 text.
- If raw YAML case-level intent conflicts with steps, pre-plan should prefer case-level intent for `verification_goal` and include a warning.
- If steps contain stale locators or outdated actions, they may still be useful as rough execution hints but must not define final success by themselves.
- If final evidence is insufficient to prove `verification_goal`, the result is `inconclusive`, not success.
- Runtime secret values must not appear in `verification_goal`, prompts, events, reports, or generated artifacts.

## Affected Specs Expected To Change

- Root `SPEC.md`: update dynamic raw case planning to mention pre-plan emits `key_actions` and `verification_goal`, and that dynamic final verification is goal-only with no configurable mode.
- `fsq_agent/models/SPEC.md`: update `Task`, `GoalPrePlan`, `AgentTaskInput`, and verification models; remove or deprecate mode-based criterion contracts.
- `fsq_agent/config/SPEC.md`: remove `VerificationSettings` / `verification.mode` and specify obsolete config rejection.
- `fsq_agent/agent/SPEC.md`: update pre-plan orchestration, prompt input, evidence-based verifier input, and verifier status rules.
- `fsq_agent/cli/SPEC.md`: update dynamic task construction so raw YAML does not create file-name-only verification goals and pre-plan owns goal summarization.
- `fsq_agent/report/SPEC.md`: update dynamic reports to display the single checked `verification_goal`.

README, example configs, launch documentation, and tests should be updated after SPEC confirmation, but they are not specification sources.

## Verification Expectations

Implementation should include tests for:

- Config containing `verification.mode` is rejected.
- Default settings no longer expose verification mode.
- `GoalPrePlan` includes `verification_goal` and `key_actions`.
- `--goal` dynamic tasks receive pre-plan-derived `key_actions` and `verification_goal` before main execution.
- Raw `--case-yaml` dynamic tasks pass full raw text into pre-plan without local YAML parsing.
- Raw YAML steps are not converted into verification criteria.
- Pre-plan instructions emphasize that raw YAML steps are advisory and may be inaccurate.
- The main task prompt renders execution key actions separately from the final verification goal.
- The verifier receives and checks only `verification_goal`.
- Key actions are not treated as independent final verification criteria.
- Dynamic recording still reconstructs replay YAML only from actual run events.
- Strict-core tests remain unaffected.

## Open Questions Resolved

- `verification_goal` is a single string, not a list.
- Pre-plan should generate both `key_actions` and `verification_goal`.
- Raw YAML dynamic execution should not locally parse YAML.
- Raw YAML steps are advisory and may be inaccurate.
- For raw YAML, pre-plan should prefer case-level intent over step details when summarizing `verification_goal`.
- `verification.mode` should be removed rather than hidden or ignored.
- Old configs containing `verification.mode` should fail loudly after implementation.

## Handoff

After this design is approved, use the `spec-driven` workflow to update the root and module `SPEC.md` files before implementation. Implementation must follow the confirmed SPEC updates, not this design document alone.