# Automation Basics

## Scope

Applies to all automation runs, regardless of harness backend or target platform.

## Execution Rules

- Use only configured harness, local, shell, or CLI tools for external actions.
- Prefer semantic actions and stable locators over coordinate-only gestures.
- Verify state-changing actions with fresh observations before claiming success.
- Treat historical artifact search as context, not proof of the current UI state.
- When a tool response indicates invalid arguments, schema mismatch, or unsupported usage, correct the same semantic action before choosing a fallback.

## Coordinate-Based Gestures

When a task or reference case includes absolute coordinates for a gesture, do not replay the numbers blindly.

- First identify which UI element, row, carousel, panel, or region the gesture is intended to operate on.
- Use a fresh UI tree or screenshot to determine the target element's actual bounds on the current device.
- Generate gesture coordinates from those current bounds, such as starting near the right-middle of the target bounds and ending near the left-middle for a forward horizontal swipe.
- If the reference coordinates came from another screen size or density, scale them only as a fallback; prefer element-relative coordinates derived from the current UI.
- A successful low-level gesture result only proves that the gesture was sent. Always verify the intended UI state afterward.

## Semantic Fidelity

- Required ordered actions define success semantics, not just final UI state.
- Recovery actions can restore state, but they do not satisfy a required semantic action unless they perform that same accepted semantic action.
- If an action is replaced by a non-equivalent fallback, record the original action as unmet in the final output.
