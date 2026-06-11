# Appium Android MCP Skill

## Scope

Use this skill only when the configured MCP server is Appium for Android. Treat it as runtime tool guidance for the current MCP configuration, not as a permanent FSQ DSL rule or cross-platform assumption.

## Tool Selection

| FSQ semantic action | Preferred Appium MCP path | Notes |
|---|---|---|
| Find visible UI | `appium_find_element`, `appium_get_text`, `appium_get_page_source` | Prefer resource id or accessibility id, then xpath. |
| Tap element | `appium_gesture` with `action=tap` and a fresh element UUID | Re-find stale elements before retrying. |
| Enter text | `appium_set_value` | Verify the target field before setting text. |
| Press key | `appium_mobile_press_key` | For each call choose exactly one key identity: either `key` or `keyCode`. Never merge examples for different keys. |
| Wait / pause | `wait_ms` | Use this for FSQ `performActions` pause and page-load waits. Do not use scroll, long_press, or any gesture as a wait substitute. |
| Screenshot evidence | `appium_screenshot` | Capture concise evidence for important assertions. |
| AI visual assertion | `appium_screenshot` then `submit_visual_assertion` | For `assertWithAI`, capture a fresh screenshot after the relevant wait/state change, then submit that screenshot path with the assertion prompt. |

## Argument Rules

- Always pass the runtime-provided non-empty `sessionId` when the tool schema exposes it.
- Do not call session management from the agent loop; session ownership belongs to runtime lifecycle.
- Do not use `appium_mobile_keyboard` as a Back or Enter substitute. It only hides or queries the software keyboard.
- Do not use gestures, close buttons, or app lifecycle cleanup as proof that a required `pressKey` action succeeded.
- Do not use gestures as waits. For FSQ `performActions` pause or page-load delays, call `wait_ms` with the required duration so waiting does not scroll, tap, long-press, or otherwise change UI state.
- For `appium_mobile_press_key`, do not send both `key` and `keyCode` in the same call. If one identity is present, omit the other field entirely.
- Treat the tool output text as the executed key. If the output says `Successfully pressed key "BACK" on Android.`, the executed key was Back even if the request also contained `keyCode: 66`.

## Correct Key Examples

Use one payload from the matching semantic action below. Do not combine fields across examples.

### `pressKey: {key: Back}`

Use this payload:

```json
{
	"keyCode": 4,
	"sessionId": "<runtime-session-id>"
}
```

### `pressKey: {key: Enter}`

Use this payload:

```json
{
	"keyCode": 66,
	"sessionId": "<runtime-session-id>"
}
```

## Invalid Mixed Key Calls

Do not call `appium_mobile_press_key` with conflicting identities:


```json
{
	"key": "BACK",
	"keyCode": 66,
	"sessionId": "<runtime-session-id>"
}
```

## Tool Usage Error Recovery

- If `appium_mobile_press_key` returns an argument validation error, rebuild the payload from the semantic action and send only the matching `keyCode` plus `sessionId`.
- If a `pressKey` step with `key: Enter` accidentally returns output for Back, do not count it as Enter. Retry Enter with `keyCode: 66` and no `key` field.
- If a `pressKey` step with `key: Back` accidentally returns output for Enter, do not count it as Back. Retry Back with `keyCode: 4` and no `key` field.
- After retrying a key action, verify the resulting UI state with a fresh observation such as page source, visible text, or screenshot evidence.
- Before `assertWithAI`, use `wait_ms` for any required pause and keep the page at the intended visual assertion state. Do not scroll or long-press merely to wait before taking the visual assertion screenshot.
- For `assertWithAI`, do not claim the visual assertion is satisfied from a screenshot path alone. Capture a fresh screenshot with `appium_screenshot`, then call `submit_visual_assertion` with the ordered key action id or label, the assertion prompt, and the fresh screenshot path before deciding whether the visual assertion is satisfied.

