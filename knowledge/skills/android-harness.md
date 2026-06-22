# Android Harness Skill

## Scope

Use this skill when the configured harness platform is Android. Treat it as runtime tool guidance for current harness action tools, not as backend-specific driver guidance.

## Tool Selection

| FSQ semantic action | Preferred runtime path | Notes |
|---|---|---|
| Launch app | `launch_app` | Use at the start of each Android case to foreground the configured target app before business actions. |
| Kill app | `kill_app` | Use at the end of each Android case after final evidence is collected to clean up app state. |
| Find visible UI | `assert_visible`, `assert_not_visible`, or current harness evidence | Prefer resource id or accessibility id, then xpath. |
| Tap element | `tap_on` | Re-evaluate stale or missing targets before retrying. |
| Enter text | `input_text` | Verify the target field before setting text. |
| Press key | `press_key` | Use the semantic key requested by the FSQ step. |
| Wait / pause | `wait_ms` | Use this for FSQ `performActions` pause and page-load waits. Do not use scroll, long_press, or any gesture as a wait substitute. |
| Screenshot evidence | current harness artifact refs or CommonTool artifact utilities when exposed | Capture concise evidence for important assertions. |
| AI visual assertion | `assert_with_ai` | For `assertWithAI`, use fresh evidence after the relevant wait/state change before deciding the assertion result. |

## Argument Rules

- Follow the active harness tool schema exactly. Do not add backend-only fields that are not exposed by the tool schema.
- Do not call session management from the agent loop; session ownership belongs to the harness and driver.
- Treat `launchApp` and `killApp` as case lifecycle setup and teardown. Use `launch_app` before the main case path and `kill_app` before finishing the case when those tools are exposed. Do not report either lifecycle action as satisfying a business key action unless the case explicitly tests launch or kill behavior.
- Do not use gestures, close buttons, or app lifecycle cleanup as proof that a required `pressKey` action succeeded.
- Do not use gestures as waits. For FSQ `performActions` pause or page-load delays, call `wait_ms` with the required duration so waiting does not scroll, tap, long-press, or otherwise change UI state.
- Treat the tool output text and harness result metadata as the executed action. If the result contradicts the intended key action, do not count it as satisfied.

## Correct Key Examples

Use one payload from the matching semantic action below. Do not combine fields across examples.

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

- If `press_key` returns an argument validation error, rebuild the payload from the active schema and the semantic action.
- If a `pressKey` step with `key: Enter` accidentally returns output for Back, do not count it as Enter. Retry Enter with the schema-valid Enter payload.
- If a `pressKey` step with `key: Back` accidentally returns output for Enter, do not count it as Back. Retry Back with the schema-valid Back payload.
- After retrying a key action, verify the resulting UI state with a fresh observation such as page source, visible text, or screenshot evidence.
- Before `assertWithAI`, use `wait_ms` for any required pause and keep the page at the intended visual assertion state. Do not scroll or long-press merely to wait before taking the visual assertion screenshot.
- For `assertWithAI`, do not claim the visual assertion is satisfied from a screenshot path alone. Use the exposed harness `assert_with_ai` action and its returned verdict before deciding whether the visual assertion is satisfied.
