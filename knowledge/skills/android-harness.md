# Android Harness Skill

Use when `harness.platform` is Android. Follow the active harness tool schema; do not rely on backend-only driver fields.

## Tool Selection

| FSQ semantic action | Preferred runtime path | Notes |
|---|---|---|
| Launch app | `launch_app` | Use at the start of each Android case to foreground the configured target app before business actions. |
| Kill app | `kill_app` | Use at the end of each Android case after final evidence is collected to clean up app state. |
| Find visible UI | `assert_visible`, `assert_not_visible`, `ui_tree`, or evidence | Prefer resource id or accessibility id, then xpath. |
| Tap element | `tap_on` | Re-evaluate stale or missing targets before retrying. |
| Enter text | `input_text` | Verify the target field before setting text. |
| Press key | `press_key` | Use the semantic key requested by the FSQ step. |
| Wait / pause | `wait_ms` | Use for FSQ pauses and page-load waits; gestures are not waits. |
| Screenshot evidence | harness artifact refs or CommonTool artifact utilities | Capture concise assertion evidence. |
| AI visual assertion | `assert_with_ai` | Wait/observe first, then use the returned verdict. |

## Argument Rules

- Follow the active harness tool schema exactly. Do not add backend-only fields.
- Do not call session management; session ownership belongs to the harness and driver.
- Treat `launchApp` and `killApp` as case lifecycle setup and teardown. Use `launch_app` before the main case path and `kill_app` before finishing the case when those tools are exposed. Do not report either lifecycle action as satisfying a business key action unless the case explicitly tests launch or kill behavior.
- Do not use gestures, close buttons, or app lifecycle cleanup as proof that a required `pressKey` action succeeded.
- Use `wait_ms` for FSQ pauses or page-load delays so waiting does not change UI state.
- Treat tool output and harness metadata as the executed action. If they contradict the intended key action, do not count it as satisfied.

## Correct Key Examples

Use one payload from the matching semantic action. Do not combine fields.

### `pressKey: {key: Back}`

Use this payload:

```json
{
  "key": "Back"
}
```

### `pressKey: {key: Enter}`

Use this payload:

```json
{
  "key": "Enter"
}
```

## Invalid Mixed Key Calls

Do not call `press_key` with conflicting or backend-only identities:

```json
{
  "key": "BACK",
  "keyCode": 66
}
```

## Tool Usage Error Recovery

- If `press_key` validation fails, rebuild the payload from the active schema and requested semantic key.
- If a `pressKey` action returns the wrong key result, do not count it. Retry the requested key with the schema-valid payload.
- After retrying a key action, verify UI state with fresh page source, visible text, or screenshot evidence.
- Before `assertWithAI`, use `wait_ms` for required pauses and keep the page at the intended visual state.
- For `assertWithAI`, do not decide from a screenshot path alone; call `assert_with_ai` and use its verdict.
