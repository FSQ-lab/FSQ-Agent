# Web Harness Skill

Use when `harness.platform` is Web. Follow the active harness tool schema; do not rely on raw Playwright APIs, JavaScript evaluation, browser tabs, network tools, storage tools, or unsupported backend-only fields.

## Tool Selection

| FSQ semantic action | Preferred runtime path | Notes |
|---|---|---|
| Open page | `navigate_to` | Use absolute URLs or configured-base relative URLs. Wait for the requested load state when the schema exposes it. |
| Go back | `navigate_back` | Use only for browser-history semantics, not as generic recovery. |
| Inspect page | `page_snapshot` | Prefer this over screenshots for locating targets and understanding page structure. |
| Click element | `click_on` | Use an exact snapshot target reference or a stable unique selector. Include `element` only as human-readable context when the schema accepts it. |
| Enter text | `type_text` | Verify the target field first when ambiguity exists. Use runtime-secret refs for sensitive values. |
| Select option | `select_option` | Use stable select targets and the option value/label requested by the task. |
| Hover element | `hover_on` | Use only when hover state is required for the next visible action. |
| Press key | `press_key` | Use the semantic key requested by the FSQ step. |
| Wait for state | `wait_for` | Use for load, visibility, hidden, timeout, or selector waits instead of unrelated UI actions. |
| Screenshot evidence | `take_screenshot` or harness artifact refs | Use screenshots for evidence and visual debugging, not as the primary target-selection substrate. |
| Verify visibility | `assert_visible` or `assert_not_visible` | Use assertion tools for required presence or absence. |
| Verify text | `assert_text` | Use deterministic text checks for required page copy or field state. |
| AI visual assertion | `assert_with_ai` | Use only for visual/page-content assertions that cannot be expressed with deterministic Web assertions. |

## Snapshot-First Rules

- Call `page_snapshot` after navigation and after state-changing actions when the next target is not already unambiguous.
- Prefer exact snapshot target references and stable selectors over coordinates or visual guessing.
- Do not infer that a page changed from a screenshot path alone. Use a fresh snapshot or assertion after the action.
- Treat screenshots as evidence artifacts. They can support debugging, but they do not replace `page_snapshot` for action targeting.
- If a target is stale or missing, refresh the snapshot once and retry the same semantic action with corrected schema-valid arguments.

## Verification and Assertion Rules

- Treat any required step phrased as verify, assert, confirm, check, ensure, or validate as an assertion requirement.
- Satisfy assertion requirements with assertion-kind tools: `assert_visible`, `assert_not_visible`, `assert_text`, or `assert_with_ai`.
- Use `assert_text` for deterministic page text or field text requirements.
- Use `assert_visible` or `assert_not_visible` for required presence or absence of page elements.
- Use `assert_with_ai` only when the assertion requires visual judgment or page interpretation that deterministic selectors/text cannot express.
- Use `page_snapshot` to inspect, locate, or collect context before an assertion, but do not count snapshot output plus agent narrative as satisfying a required assertion.
- If a required assertion fails, report the assertion as unmet. Do not recover with unrelated navigation or alternate actions unless the task explicitly permits recovery before that assertion.

## Argument Rules

- Follow the active harness tool schema exactly. Do not add raw Playwright MCP, locator engine, JavaScript, network, storage, file upload, drag/drop, PDF, tab, or devtools fields unless the active schema exposes them.
- Use `wait_for` for waits so waiting does not change page state.
- Keep sensitive text out of tool arguments unless it is provided through a runtime-secret reference.
- Treat tool output and harness metadata as the executed action. If they contradict the intended key action, do not count it as satisfied.

## Correct Key Examples

Use one payload from the matching semantic action. Do not combine unrelated fields.

### `pressKey: {key: Enter}`

Use this payload:

```json
{
  "key": "Enter"
}
```

### `typeText` with a runtime secret

Use this payload:

```json
{
  "target": "Password field",
  "text": {
    "runtimeSecret": "TEST_ACCOUNT_PASSWORD"
  }
}
```

## Unsupported Capability Families

The first Web harness batch intentionally excludes raw JavaScript evaluation, generated Playwright test code, network interception, browser storage, devtools, tabs, drag/drop, file upload, PDF, and coordinate/vision-only capabilities. Do not ask for or simulate those capabilities with unrelated tools; report the limitation when the task requires one.

## Tool Usage Error Recovery

- If a Web tool validation fails, rebuild the payload from the active schema and the requested semantic action.
- If an action executes but the expected state is not present, take a fresh `page_snapshot`, then decide whether retrying the same semantic action is justified.
- If a key action returns the wrong page state, do not count it. Retry the requested key/action with schema-valid payload or report the mismatch.
- Before `assert_with_ai`, use `wait_for` for required waits and keep the page at the intended visual state.
- For `assert_with_ai`, use the returned verdict rather than deciding from screenshot existence.