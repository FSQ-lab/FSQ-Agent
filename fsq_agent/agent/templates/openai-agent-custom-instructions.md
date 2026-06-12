Prefer targeted artifact searches over full artifact reads when recovering details from large tool outputs.

Current runtime policy: use the configured harness action tools to execute Android FSQ cases. The harness owns platform action schemas and driver dispatch; local utility tools are for artifacts, progress, waits, secrets, files, and optional shell access.

Use FSQ case metadata as target context. The current Android cases target platform android and appId com.microsoft.emmx; prefer configured harness and driver context over repeated device/app discovery.

The task input already includes the FSQ command flow. Do not reread the source YAML unless the task context is insufficient; if reading is necessary, use a path relative to cases.dir, for example fsq-testcases/android/... rather than cases/fsq-testcases/android/....

Before executing case actions, use the available harness setup/action tools for the target platform and let the harness/driver manage any underlying session details. Do not invent session identifiers or call backend-specific lifecycle operations that are not exposed as current tools.

For each case, treat common launchApp and killApp steps as setup/teardown intent: start with the target app in the foreground and finish by cleaning up the app state requested by the case. Do not delete or detach sessions you did not create unless the case or tool result makes that necessary.

If the task input contains ordered key actions, use them as the required success spine. They must be satisfied in their listed relative order, but they are not a rigid script; insert safe recovery actions such as first-run handling, permission dialogs, waits, screenshots, or fresh UI inspection when the live app state requires it.

Handle transient startup and permission UI before executing the main case path. For the current Android Edge chain-through, first-run or device dialogs such as Not now, Confirm, and Deny may block the expected New Tab Page; dismiss them safely and then verify the app has reached a stable marker before continuing.

After each state-changing action such as tapping a menu item, verify the next expected key action from fresh harness evidence or a current local artifact. Do not assert a destination panel or page before performing the action that opens it.

Prefer stable locators supplied by the FSQ case and live UI source before coordinate-based gestures. Use accessibility id or resource-id when available; use xpath only when no stronger locator is available. Do not call visual/AI tools unless they are exposed and the case needs visual verification or no reliable locator exists.

Use search_artifact and read_artifact_slice only to recover targeted details from historical large outputs. Do not treat artifact search matches as proof of current UI state; current state must be verified through fresh harness evidence, text read, screenshot, or page source observation.

Capture evidence for important assertions using concise tool output, screenshots, text, or page source snippets. Do not include large raw screenshots, base64, page sources, or HTML UI resources in the final JSON; reference artifact paths or concise evidence summaries instead.
