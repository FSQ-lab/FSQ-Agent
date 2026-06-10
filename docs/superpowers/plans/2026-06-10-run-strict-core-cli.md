# Run Strict Core CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CLI command for running one Android FSQ YAML case through the strict deterministic core path and generating evidence plus core reports.

**Architecture:** The command is a thin entry adapter. It loads settings and FSQ metadata, constructs `UiAutomator2AndroidDriver`, `ArtifactStore`, and `AndroidHarness`, then calls the existing `run_strict_fsq_core_case` helper. It must not add recovery, locator fallback, AI behavior, or report layout logic.

**Tech Stack:** Click, pytest monkeypatching, existing config/settings, `FsqCaseLoader`, `AndroidHarness`, `UiAutomator2AndroidDriver`, `ArtifactStore`, and `run_strict_fsq_core_case`.

---

### File Structure

- Modify: `fsq_agent/cli/SPEC.md`
- Modify: `fsq_agent/cli/_main.py`
- Modify: `tests/test_cli.py`
- Create: `docs/superpowers/plans/2026-06-10-run-strict-core-cli.md`

### Task 1: Write Failing CLI Tests

**Files:**
- Modify: `tests/test_cli.py`

- [x] **Step 1: Register command test**

Assert `run-strict-core` exists in `main.commands`.

- [x] **Step 2: Command behavior test**

Use `click.testing.CliRunner`, a temporary config/case, and monkeypatches for `UiAutomator2AndroidDriver` and `run_strict_fsq_core_case`. Assert the command passes the resolved case path, run directory, run id, Android serial, and app id into the strict helper/harness construction, then prints `core-report.md` and `evidence-manifest.json` paths.

- [x] **Step 3: Verify red**

Run: `pytest tests/test_cli.py -q`

Expected: FAIL because `run-strict-core` is not registered.

### Task 2: Implement CLI Command

**Files:**
- Modify: `fsq_agent/cli/_main.py`

- [x] **Step 1: Import dependencies**

Import `AndroidHarness`, `ArtifactStore`, `UiAutomator2AndroidDriver`, `FsqCaseLoader`, `run_strict_fsq_core_case`, and `_resolve_task_path`.

- [x] **Step 2: Add command**

Add `@main.command("run-strict-core")` with options `--task`, `--android-serial`, `--app-id`, `--run-id`, `--config`, and `--workspace`.

- [x] **Step 3: Resolve app id and output paths**

Load settings, resolve task path against `settings.cases.dir`, load the FSQ case to get `config.app_id`, derive run id from provided option or case id, and use `settings.output.runs_dir / run_id`.

- [x] **Step 4: Execute strict helper and log paths**

Construct driver/harness/store, call `run_strict_fsq_core_case`, then log report and manifest paths.

### Task 3: Verify And Commit

**Files:**
- Modified files from Tasks 1-2.

- [x] **Step 1: Run related tests**

Run: `pytest tests/test_cli.py tests/test_cli_core_execution.py -q`

Expected: PASS.

- [x] **Step 2: Run full suite and diff check**

Run: `pytest -q`

Expected: PASS.

Run: `git diff --check`

Expected: no output and exit code 0.

- [x] **Step 3: Commit**

Run:

```bash
git add fsq_agent/cli/SPEC.md fsq_agent/cli/_main.py tests/test_cli.py docs/superpowers/plans/2026-06-10-run-strict-core-cli.md
git commit -m "feat: add strict core CLI command"
```

### Self-Review

- Spec coverage: The plan implements the CLI command documented in CLI SPEC.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation steps remain.
- Type consistency: The command delegates to existing helpers and returns no new shared model.
