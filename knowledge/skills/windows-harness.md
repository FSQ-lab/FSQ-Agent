# Windows Harness Skill

Use when `harness.platform` is Windows. Follow the active harness tool schema; do not rely on raw pywinauto APIs, coordinate-only clicking, shell commands, or unsupported backend-only fields.

## Tool Selection

| FSQ semantic action | Preferred runtime path | Notes |
|---|---|---|
| Launch app | `launch_app` | Launch the configured desktop application. The app path and launch args come from configuration; do not hardcode machine paths in arguments. |
| Close app | `kill_app` | Use only to stop the launched application, typically as teardown. |
| Inspect window | `ui_snapshot` | Prefer this over screenshots for locating controls and understanding the window control tree. |
| Click control | `click_on` | Use a control locator (`title`, `control_type`, `automation_id`, `class_name`, `index`) or an exact snapshot `target`. Set `double`/`button` only when the action requires it. |
| Double-click control | `double_click_on` | Use when a double-click is explicitly required. |
| Right-click control | `right_click_on` | Use for context-menu semantics, not as generic recovery. |
| Enter text | `type_text` | Resolve the target control first when ambiguous. Use `clear: true` to replace existing text. Use runtime-secret refs for sensitive values. |
| Press key | `press_key` | Use pywinauto key syntax for the semantic key/shortcut requested by the FSQ step, for example `^s` for Ctrl+S or `{ENTER}`. |
| Verify visibility | `assert_visible` or `assert_not_visible` | Use assertion tools for required presence or absence of a control. |
| AI visual assertion | `assert_with_ai` | Use only for visual/window-content assertions that cannot be expressed with deterministic Windows assertions. |

## Snapshot-First Rules

- Call `ui_snapshot` after launch and after state-changing actions when the next target is not already unambiguous.
- Prefer stable control locators (`automation_id`, then `title` + `control_type`) over `index` or visual guessing.
- Use `index` (1-based) only to disambiguate when multiple controls share the same locator fields.
- Do not infer that the window changed from a screenshot path alone. Use a fresh `ui_snapshot` or assertion after the action.
- Treat screenshots as evidence artifacts. They can support debugging, but they do not replace `ui_snapshot` for action targeting.
- If a target is stale or missing, refresh the snapshot once and retry the same semantic action with corrected schema-valid arguments.

## Control Locator Rules

- A control locator may combine `title`, `control_type`, `automation_id`, `class_name`, and `index`.
- `title` matches the control name; `control_type` is the UIA control type (for example `Button`, `Edit`, `Document`, `Tab`); `automation_id` is the stable UIA automation id; `class_name` is the native class.
- Extract `control_type` from the actual `ui_snapshot` output. Do not assume a control type from the displayed text.
- Prefer `automation_id` when available because it is the most stable. Fall back to `title` + `control_type` when it is not.

## Verification and Assertion Rules

- Treat any required step phrased as verify, assert, confirm, check, ensure, or validate as an assertion requirement.
- Satisfy assertion requirements with assertion-kind tools: `assert_visible`, `assert_not_visible`, or `assert_with_ai`.
- Use `assert_visible` or `assert_not_visible` for required presence or absence of a control.
- Use `assert_with_ai` only when the assertion requires visual judgment or window interpretation that deterministic control checks cannot express.
- Use `ui_snapshot` to inspect, locate, or collect context before an assertion, but do not count snapshot output plus agent narrative as satisfying a required assertion.
- If a required assertion fails, report the assertion as unmet. Do not recover with unrelated actions unless the task explicitly permits recovery before that assertion.

## Argument Rules

- Follow the active harness tool schema exactly. Do not add raw pywinauto, coordinate, drag/drop, scroll, shell, registry, or window-management fields unless the active schema exposes them.
- Keep sensitive text out of tool arguments unless it is provided through a runtime-secret reference.
- Treat tool output and harness metadata as the executed action. If they contradict the intended key action, do not count it as satisfied.

## Correct Key Examples

Use one payload from the matching semantic action. Do not combine unrelated fields.

### `clickOn` with a control locator

Use this payload:

```json
{
  "locator": {
    "title": "Save",
    "control_type": "Button"
  }
}
```

### `pressKey: {key: ^s}`

Use this payload:

```json
{
  "key": "^s"
}
```

### `typeText` with a runtime secret

Use this payload:

```json
{
  "locator": {
    "control_type": "Edit",
    "automation_id": "PasswordBox"
  },
  "text": {
    "runtimeSecret": "TEST_ACCOUNT_PASSWORD"
  }
}
```

## Unsupported Capability Families

The first Windows harness batch intentionally excludes drag/drop, scrolling, coordinate-only interaction, window resize/move, shell or process control beyond launch/kill, registry access, and file dialogs as dedicated tools. Do not ask for or simulate those capabilities with unrelated tools; report the limitation when the task requires one.

## Tool Usage Error Recovery

- If a Windows tool validation fails, rebuild the payload from the active schema and the requested semantic action.
- If an action executes but the expected state is not present, take a fresh `ui_snapshot`, then decide whether retrying the same semantic action is justified.
- If a key action returns the wrong window state, do not count it. Retry the requested key/action with a schema-valid payload or report the mismatch.
- Before `assert_with_ai`, keep the window at the intended visual state.
- For `assert_with_ai`, use the returned verdict rather than deciding from screenshot existence.
