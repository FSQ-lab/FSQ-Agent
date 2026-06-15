# Config Structure Follow-up Design

## Goal

Address two configuration shape issues after the config/env simplification:

1. Restore a YAML-controlled execution interval for strict-core and recorded-case replay.
2. Group related skill and knowledge configuration into one structured top-level block.

## Scope

This change only affects developer-owned YAML configuration and the settings/path resolution layer that feeds existing runtime code. It does not move secrets, Android app id, Android serial, or Azure provider values back into YAML.

## Proposed YAML Shape

Use `harness.strict_core.step_interval_seconds` for deterministic strict-core pacing. This follows the user's direction that the execution interval belongs with harness configuration rather than a separate recording or execution block.

```yaml
harness:
  platform: android
  android:
    backend: uiautomator2
  strict_core:
    step_interval_seconds: 1.0
```

Use `agent_context` to group the agent's knowledge root and the resources stored under it. Skills are loaded from the knowledge directory today, so the configuration should model them as knowledge-root resources rather than as a parallel top-level list:

```yaml
agent_context:
  knowledge:
    root_dir: ./knowledge
    skills:
      dir: skills
      items:
        - name: automation-basics
          description: Semantic action and evidence guidance for local runs.
          kind: markdown
          path: automation-basics.md
          required: true
        - name: android-harness
          description: Android harness action selection and recovery guidance.
          kind: markdown
          path: android-harness.md
          required: true
    pre_plan:
      dir: project_android_v1
```

## Behavior

- `harness.strict_core.step_interval_seconds` controls the interval passed to `StepSequenceRunner` for strict-core execution, including replaying generated recorded strict cases.
- The interval defaults to `1.0` seconds, must be non-negative, and does not create `waitMs` commands or synthetic evidence steps.
- `agent_context.knowledge.root_dir` replaces the old top-level `knowledge_dir` YAML key.
- `agent_context.knowledge.skills.dir` defaults to `skills` and resolves under `agent_context.knowledge.root_dir` when relative.
- `agent_context.knowledge.skills.items` replaces the old top-level `skills` YAML key. Each item path resolves under the resolved skills directory, preserving the existing `knowledge/skills/*.md` layout.
- `agent_context.knowledge.pre_plan.dir` replaces the old `pre_plan.knowledge_dir` YAML key. Relative values resolve under `agent_context.knowledge.root_dir`, so `project_android_v1` means `./knowledge/project_android_v1`.
- If `agent_context.knowledge.pre_plan.dir` is omitted, pre-plan falls back to `agent_context.knowledge.root_dir`.
- Existing internal call sites may continue using `settings.skills`, `settings.knowledge_dir`, and `settings.pre_plan.knowledge_dir` through compatibility properties on the settings aggregate, but old YAML keys are rejected.

## Affected SPEC Files

- `fsq_agent/config/SPEC.md`: YAML shape, path resolution, harness strict-core interval ownership.
- `fsq_agent/models/SPEC.md`: settings model contracts for `agent_context`, knowledge grouping, and harness strict-core settings.
- `fsq_agent/cli/SPEC.md`: strict-core execution passes configured harness pacing to the core runner.
- `fsq_agent/core/SPEC.md`: `StepSequenceRunner` already supports `step_interval_seconds`; clarify that entry layers may supply the value from config.
- Root `SPEC.md`: module table update only if wording needs to mention grouped agent context.

## Non-goals

- No env key changes.
- No reintroduction of `strict_core` as a top-level YAML block.
- No CLI flag for step interval.
- No support for multiple skill roots or multiple knowledge profiles in this change.
- No backward-compatible migration for the old pre-release YAML keys beyond schema rejection.

## Verification Expectations

- `config.example.yaml` and `config.local.yaml` use the new `harness.strict_core` and knowledge-root-centered `agent_context` structure.
- Settings loading rejects old top-level `skills`, `knowledge_dir`, and `pre_plan` YAML keys.
- Settings loading resolves `agent_context.knowledge.root_dir` relative to the config file, then resolves relative skills and pre-plan directories under that root.
- Strict-core CLI execution passes `harness.strict_core.step_interval_seconds` into `StepSequenceRunner`.
- Tests cover default interval, configured interval, zero interval, invalid negative interval, and new agent context path resolution.
