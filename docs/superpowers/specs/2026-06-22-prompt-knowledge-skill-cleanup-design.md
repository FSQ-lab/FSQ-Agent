# Prompt, Knowledge, and Skill Cleanup Design

## Goal

Make dynamic LLM execution prompts clearer, shorter, and easier to maintain by removing the separate custom-instruction channel, keeping loader diagnostics out of model context, and optimizing the existing runtime Markdown knowledge files for their intended prompt roles.

The desired prompt architecture is:

```text
agent_instructions.j2 = stable dynamic execution contract
task_input.j2         = one task's structured input, key actions, and verification goal
knowledge/project.md  = project-specific guidance for the tested application
knowledge/skills/*.md = independently configured, composable execution guidance
page knowledge        = pre-plan page graph loaded through pre-plan tools as needed
```

## Scope

This design covers:

- Removing `custom_instructions` and `custom_instructions_path` as supported prompt configuration.
- Removing custom-instruction rendering and prompt-model fields.
- Preventing skill and knowledge loader warnings from being sent to LLM prompts.
- Changing optional skill failures to skip the broken skill and log/emit diagnostics instead of passing warning-only bundles to the model.
- Keeping required skill failures as fail-fast configuration/runtime errors.
- Reviewing and optimizing current runtime Markdown content under `knowledge/`.
- Aligning default prompt text with current CommonTool and harness capabilities.

## Non-Goals

This design does not cover:

- Changing the OpenAI Agents SDK runner, provider selection, or harness action schema design.
- Changing dynamic pre-plan output schemas such as `GoalPrePlan`.
- Changing strict-core FSQ execution behavior.
- Rebuilding the page-knowledge schema from Markdown/JSON into a different storage format.
- Adding new tools or restoring shell, CLI, or public visual assertion tools.
- Updating `SPEC.md` files or implementation directly from this document.

## Existing Content Audit

The current configured runtime knowledge root is `knowledge/`.

### Main Execution Knowledge

`knowledge/project.md` is loaded for every normal dynamic task as private project knowledge. It currently contains useful Edge Android guidance for:

- Overflow menu horizontal paging.
- Microsoft account password sign-in flow.
- Runtime secret use for `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD`.

It also contains a loader-oriented note about `knowledge/index.md` being reserved for page knowledge. That is implementation metadata, not project guidance, and should not be sent to the LLM.

### Configured Skills

Current configured skills are:

- `knowledge/skills/automation-basics.md`
- `knowledge/skills/android-harness.md`

`automation-basics.md` is short and useful, but it currently says to use configured harness, local, shell, or CLI tools. Shell and CLI execution are not part of the current runtime tool contract, so this should be corrected to configured harness tools and CommonTool utilities.

`android-harness.md` contains useful Android harness guidance, but it includes stale guidance for `submit_visual_assertion when exposed`. Current behavior is that authored Android `assertWithAI` is handled by the harness-owned `assert_with_ai` platform action; public/common `submit_visual_assertion` is not a runtime tool contract.

Both skill files overlap with the default agent template on fresh observations, stale artifacts, semantic fidelity, and tool-usage error recovery. The optimized design should place each rule in one primary location and keep cross-references short.

### Page Knowledge

`knowledge/project_android_v1/index.md` is the pre-plan page-knowledge index. It is not loaded into the main execution prompt. It currently references all 14 page Markdown files under `knowledge/project_android_v1/pages/`; no orphan page Markdown files were found.

The page Markdown files are structured JSON page nodes. They are generally useful for pre-plan page lookup, but many locator notes include historical phrases such as `successful run`, `observed run`, or `failed run`. These should be compressed into current planning facts:

- What the locator identifies.
- Why its confidence is high, medium, or low.
- What limitation or conditional behavior matters.
- Whether a path is confirmed or only a weak planning hint.

The low-confidence `All menu` path in `edge_android_overflow_menu.md` may remain only if it is clearly marked as a weak planning hint, not a verified route or success criterion.

All referenced page image assets currently exist. This design does not remove them, but image descriptions should remain concise and not become historical narratives.

## Proposed Design

### 1. Remove The Custom Instruction Channel

`custom_instructions` and `custom_instructions_path` should no longer exist as supported configuration or prompt model fields.

Implementation expectations after SPEC confirmation:

- Remove `custom_instructions` and `custom_instructions_path` from `OpenAIAgentPromptConfig`.
- Remove path resolution for `prompt.custom_instructions_path`.
- Remove `AgentPromptModel.custom_instructions`.
- Remove `PromptModelBuilder._custom_instructions`.
- Remove the `Custom operator instructions` block from `agent_instructions.j2`.
- Remove references that describe tool-specific guidance as coming from custom operator instructions.
- Update tests that currently assert custom-instruction rendering or file loading.
- Ensure configs containing `openai_agents.prompt.custom_instructions` or `openai_agents.prompt.custom_instructions_path` fail validation.

Rationale: project-specific instructions belong in `knowledge/project.md`; reusable execution guidance belongs in configured skills. A third ad hoc prompt channel creates unclear precedence and encourages duplicated, stale prompt text.

### 2. Keep Loader Diagnostics Out Of LLM Context

Loader diagnostics are operational signals, not useful execution instructions. They should not be included in the model-facing prompt.

Implementation expectations after SPEC confirmation:

- Remove `knowledge_warnings` rendering from `agent_instructions.j2`.
- Remove `skill.warnings` rendering from `agent_instructions.j2`.
- Do not include skill warnings in pre-plan `skills` JSON input.
- Prefer logging and run events for optional skill skips and knowledge-reference diagnostics.
- Keep pre-plan model-generated planning warnings in `GoalPrePlan`; those are different from loader warnings and remain part of planning output.

Rationale: LLMs should receive complete, trustworthy guidance. Missing-file diagnostics can distract the model and make it reason about system state instead of the test flow.

### 3. Skill Loading Semantics

Configured skills should be either complete and model-visible, or excluded from model context.

Required skills:

- Missing `path` and missing inline `content` should fail fast.
- Missing file, unreadable file, invalid directory, or other load failure should fail fast.
- No partial or warning-only `SkillBundle` should be passed to the LLM.

Optional skills:

- Missing `path` plus missing inline `content` should skip the skill and log/emit a diagnostic.
- Missing file or unreadable file should skip the skill and log/emit a diagnostic.
- Skipped optional skills should not appear in main execution prompt or pre-plan input.

Successful skills:

- A successfully loaded skill contributes only `name`, `description`, and `instructions` to model context.
- Skill file metadata may remain available internally for diagnostics, but does not need to be rendered into the prompt.

Rationale: the existing `required` flag should control whether a broken skill is fatal. Optional skills should not degrade prompt quality with warnings or empty sections.

### 4. Main Agent Prompt Structure

The default `agent_instructions.j2` should be a compact execution contract.

It should keep:

- Non-interactive single-task execution boundary.
- Use of configured harness tools and CommonTool utilities only.
- `key_actions` as ordered execution guidance.
- `verification_goal` as the only final success target.
- Fresh-observation requirement after state-changing actions.
- Final structured output contract.
- Short boundaries for source case mutation, secrets, artifacts, and evidence.
- Separate rendered blocks for project knowledge and successfully loaded skills.

It should remove or reduce:

- Custom instruction references.
- Knowledge warning and skill warning sections.
- Repeated explanations also owned by skills.
- Stale references to shell, CLI tools, or public `submit_visual_assertion`.
- Long general-purpose prose that does not directly affect execution behavior.

The prompt should avoid duplicate phrasing across the template and skill files. If a rule is core to all dynamic runs, keep the concise version in `agent_instructions.j2`. If a rule is platform-specific or tool-specific, keep it in the appropriate skill.

### 5. Task Input Prompt Structure

`task_input.j2` should remain focused on one task:

- Structured `AgentTaskInput` JSON.
- Ordered key actions.
- One final verification goal.

It should not carry long-lived policy text that belongs in `agent_instructions.j2`, `project.md`, or skills. The task prompt may repeat the key distinction that key actions are execution guidance and `verification_goal` is the final target, but it should not restate broader execution policy.

### 6. Project Knowledge Content Cleanup

`knowledge/project.md` should be rewritten as concise Edge Android project guidance.

Keep:

- Overflow menu paging behavior and need for fresh observation after horizontal menu swipes.
- Microsoft account sign-in route, including alternate sign-in options before password entry.
- Secret handling for `TEST_ACCOUNT_EMAIL` and `TEST_ACCOUNT_PASSWORD` through `get_runtime_secret` only.
- Account-dependent flow evidence expectations.

Remove:

- Loader implementation notes such as reserved index paths.
- Generic automation rules already in the default agent prompt or skills.
- Any text that describes repository layout instead of tested-product behavior.

### 7. Skill Content Cleanup

`automation-basics.md` should be platform-independent and concise.

Keep:

- Prefer semantic actions and stable locators.
- Verify state-changing actions with fresh observations.
- Treat historical artifact search as context, not current proof.
- Correct schema/usage errors for the same semantic action before fallback.
- Element-relative coordinate guidance for coordinate-derived gestures.
- Semantic fidelity for ordered actions.

Change:

- Replace references to shell or CLI tools with configured harness tools and CommonTool utilities.
- Remove duplicate wording already stated in `agent_instructions.j2` unless the skill adds practical detail.

`android-harness.md` should be Android-specific harness guidance.

Keep:

- Android action-to-tool selection table.
- Schema-following and session-ownership rules.
- Lifecycle setup/teardown semantics.
- `press_key` examples for `Back` and `Enter`.
- `wait_ms` for authored waits or pauses.
- `assert_with_ai` as the path for Android visual assertions.

Change:

- Remove `submit_visual_assertion` references.
- Remove any suggestion that shell, CLI, backend-only session management, or private driver fields are available to the model.
- Keep examples minimal and only for frequent failure modes.

### 8. Page Knowledge Content Cleanup

The page knowledge graph should stay pre-plan-oriented and concise.

For `index.md`:

- Keep page ids, file paths, names, and intent keywords.
- Avoid embedding execution rules.
- Keep intents short and search-friendly.

For `pages/*.md`:

- Preserve the JSON node structure.
- Keep identifiers, elements, reference locators, operations, and `to_page_id` transitions.
- Rewrite historical notes into present-tense planning facts.
- Use confidence and notes to express uncertainty rather than narrative.
- Keep low-confidence paths explicit and non-authoritative.
- Avoid duplicating generic prompt or skill rules.

Example rewrite direction:

```text
Before: Used in two successful open/return cycles.
After: Primary text locator for the Downloads menu item.

Before: Observed in a failed run; include as a weak planning hint only.
After: Low-confidence hint; do not rely on this path unless live UI confirms it.
```

## Error Handling And Observability

- Required skill load failures should continue to fail before LLM execution.
- Optional skill skips should be visible to operators through logs and, where available, run events.
- Loader warnings should not be sent as prompt text.
- If all configured skills are optional and all are skipped, the run may continue with project knowledge and default instructions, but logs/events must make the missing guidance clear.
- If `custom_instructions` or `custom_instructions_path` appears in config, validation should fail with an actionable message that says to move guidance into `knowledge/project.md` or configured skills.

## Affected Specifications

Expected SPEC updates after this design is approved:

- Root `SPEC.md`: no architecture change expected, but verify module descriptions remain accurate.
- `fsq_agent/models/SPEC.md`: remove custom instruction fields from `OpenAIAgentPromptConfig`; clarify prompt variables/template paths remain supported if still intended.
- `fsq_agent/config/SPEC.md`: remove custom instruction config keys and document rejection of obsolete keys.
- `fsq_agent/skills/SPEC.md`: update optional-skill skip semantics and required-skill fail-fast behavior.
- `fsq_agent/knowledge/SPEC.md`: clarify loader diagnostics are not prompt content.
- `fsq_agent/agent/SPEC.md`: update prompt model assembly, warning handling, and default template responsibilities.

## Implementation Expectations After SPEC Confirmation

Expected implementation areas:

- Settings model and config path resolution.
- Config obsolete-key rejection or narrowed schema tests.
- Prompt model dataclasses and builder.
- Default agent template.
- Pre-plan input construction for skills.
- Skill loader return behavior and logging/event reporting path.
- Runtime knowledge and skill Markdown content under `knowledge/`.
- Tests for prompt rendering, config rejection, skill loading, and knowledge content invariants.

Implementation should stay scoped to prompt/knowledge/skill behavior. It should not change provider selection, harness construction, task planning schema, final verification schema, or strict-core execution.

## Verification Expectations

After implementation, verify:

- Config with `openai_agents.prompt.custom_instructions` fails.
- Config with `openai_agents.prompt.custom_instructions_path` fails.
- Default main agent instructions do not contain `Custom operator instructions`.
- Default main agent instructions do not contain `Knowledge warnings` or `Skill warnings` sections.
- Pre-plan input contains only successfully loaded skill instructions and does not include skill loader warnings.
- Required broken skill fails fast.
- Optional broken skill is skipped, logged/emitted, and absent from model-facing context.
- Successfully loaded skills and `knowledge/project.md` still reach the main execution prompt.
- Existing configured skills still load from `knowledge/skills`.
- Prompt content no longer mentions shell/CLI tools as available runtime actions.
- Prompt content no longer mentions public/common `submit_visual_assertion`.
- All page Markdown files remain referenced by `knowledge/project_android_v1/index.md`.
- Page knowledge can still be read by page id through pre-plan tools.
- Main dynamic, pre-plan, and verification tests still enforce that `verification_goal` is the final target and key actions are execution guidance.

## Open Questions Resolved

- `custom_instructions` should not remain as a supported compatibility feature. Project and skill knowledge replace it.
- Optional broken skills should be skipped with logs/events and not passed to the LLM.
- Required broken skills should fail fast.
- Prompt optimization must include actual runtime Markdown content cleanup, not just loader and template restructuring.
- Page knowledge is not obsolete. It is pre-plan-only, and all current page Markdown files are indexed.

## User Review Gate

This design should be reviewed before any SPEC or implementation changes. After approval, use `spec-driven` to translate the design into root/module `SPEC.md` updates.
