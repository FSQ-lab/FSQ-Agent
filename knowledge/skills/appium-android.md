# Android Platform Action Skill

## Scope

Use this skill when the configured harness is Android with Appium automation. Treat it as runtime guidance for FSQ Android platform actions, not as backend transport guidance.

## Action Selection

| FSQ semantic action | Preferred platform action | Notes |
|---|---|---|
| Find visible UI | `android_find_element` | Prefer `strategy` + `selector` or known `element_id`; use `target` only as a convenience fallback. |
| Tap element | `android_tap` | Prefer direct `element_id` or `strategy` + `selector`; do not call `android_find_element` first unless you need the id for multiple follow-up reads/actions. |
| Scroll until visible | `android_scroll_to_element` | Use this instead of repeated find/screenshot/manual scroll loops. |
| Read current UI tree | `android_page_source` | Use sparingly for targeted diagnosis when locators are unclear; it returns bounded XML text. |
| Read element state | `android_get_text` / `android_get_attribute` | Use this for text, enabled, displayed, checked, clickable, content-desc, resource-id, and class checks. |
| Enter text | `android_input_text` | Prefer direct `element_id` or `strategy` + `selector`; use `w3c_actions` only for the focused control. |
| Press key | `android_press_key` | Use one clear semantic key per call, such as Back or Enter. |
| Wait / pause | `wait_ms` or `android_wait` | Use a pure wait for FSQ pause and page-load waits. Do not use gestures as a wait substitute. |
| Screenshot evidence | `android_screenshot` | Capture concise evidence for important assertions. |
| AI visual assertion | `android_screenshot` then `submit_visual_assertion` | Capture a fresh screenshot after the relevant wait/state change, then submit that screenshot path with the assertion prompt. |

## Argument Rules

- Do not manage Android automation sessions from the agent loop; session and app lifecycle are harness responsibilities.
- Do not call lifecycle-only actions directly. The harness owns app activation, app termination, keyboard cleanup, alert cleanup, session creation, and session deletion.
- Prefer exact locator arguments in this order: `element_id` from a fresh result, `strategy` + `selector`, then `target` fallback. For Android, prefer accessibility id, then resource id, then `-android uiautomator`; use xpath only as a last resort.
- Use action composition inside platform actions. For example, call `android_tap` with `strategy` + `selector` directly instead of doing `android_find_element` and then `android_tap` unless the same element id will be reused.
- Do not invent coordinate fields for `android_tap`; it is an element/locator tap action.
- If an element may be off-screen, call `android_scroll_to_element` with the best locator rather than repeated failed finds.
- Do not use keyboard cleanup as a Back or Enter substitute.
- Do not use gestures, close buttons, or app lifecycle cleanup as proof that a required `pressKey` action succeeded.
- Do not use gestures as waits. For FSQ `performActions` pause or page-load delays, call `wait_ms` or `android_wait` so waiting does not scroll, tap, long-press, or otherwise change UI state.
- Treat platform action output as the executed action evidence. If a key action returns output for a different key than requested, do not count it as satisfying the original key action.

## Correct Key Examples

Use one payload from the matching semantic action below. Do not combine fields across examples.

### `pressKey: Back`

```json
{
	"key": "Back"
}
```

### `pressKey: Enter`

```json
{
	"key": "Enter"
}
```

## Action Error Recovery

- If `android_press_key` returns an argument validation error, rebuild the payload from the semantic action and send only the matching key.
- If a `pressKey: Enter` step returns output for Back, do not count it as Enter. Retry Enter with a clear Enter key payload.
- If a `pressKey: Back` step returns output for Enter, do not count it as Back. Retry Back with a clear Back key payload.
- After retrying a key action, verify the resulting UI state with a fresh observation such as visible text, element lookup, or screenshot evidence.
- Before `assertWithAI`, use `wait_ms` or `android_wait` for any required pause and keep the page at the intended visual assertion state. Do not scroll or long-press merely to wait before taking the visual assertion screenshot.
- For `assertWithAI`, do not claim the visual assertion is satisfied from a screenshot path alone. Capture a fresh screenshot with `android_screenshot`, then call `submit_visual_assertion` with the ordered key action id or label, the assertion prompt, and the fresh screenshot path before deciding whether the visual assertion is satisfied.
