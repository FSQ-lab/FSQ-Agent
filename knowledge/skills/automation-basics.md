# Automation Basics

## Scope

Applies to all automation runs, regardless of harness backend or target platform.

## Execution Rules

- Use only configured harness, local, shell, or CLI tools for external actions.
- Prefer semantic actions and stable locators over coordinate-only gestures.
- Verify state-changing actions with fresh observations before claiming success.
- Treat historical artifact search as context, not proof of the current UI state.
- When a tool response indicates invalid arguments, schema mismatch, or unsupported usage, correct the same semantic action before choosing a fallback.

## Semantic Fidelity

- Required ordered actions define success semantics, not just final UI state.
- Recovery actions can restore state, but they do not satisfy a required semantic action unless they perform that same accepted semantic action.
- If an action is replaced by a non-equivalent fallback, record the original action as unmet in the final output.
