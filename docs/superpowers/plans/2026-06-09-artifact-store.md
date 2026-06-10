# Artifact Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `ArtifactStore` to own run-local evidence artifact directory policy and return portable `EvidenceArtifactRef` values.

**Architecture:** `ArtifactStore` lives in `fsq_agent/core/evidence/_artifact_store.py` and is exported from `fsq_agent.core.evidence` and `fsq_agent.core`. It writes files under a caller-provided run directory and returns model-owned `EvidenceArtifactRef` values with paths relative to that run directory. `EvidenceRecorder` continues to only consume refs and write the manifest.

**Tech Stack:** Python, pathlib, json, pytest, Pydantic evidence models.

---

## File Structure

- Modify `fsq_agent/core/SPEC.md`: document artifact directory policy and `ArtifactStore` API.
- Create `fsq_agent/core/evidence/_artifact_store.py`: implement artifact path policy and JSON/text/bytes writing helpers.
- Modify `fsq_agent/core/evidence/__init__.py`: export `ArtifactStore`.
- Modify `fsq_agent/core/__init__.py`: export `ArtifactStore`.
- Create `tests/test_artifact_store.py`: tests for directory layout, relative refs, JSON/text/bytes writing, and name normalization.

### Task 1: JSON Artifact Writing

**Files:**
- Create: `tests/test_artifact_store.py`
- Create: `fsq_agent/core/evidence/_artifact_store.py`
- Modify: `fsq_agent/core/evidence/__init__.py`
- Modify: `fsq_agent/core/__init__.py`

- [x] **Step 1: Write failing JSON artifact test**

Create a test that imports `ArtifactStore`, writes a `ui_tree` JSON artifact for `step-1` / `finalize`, asserts the file lands under `artifacts/ui-trees/`, asserts JSON content, and asserts returned `EvidenceArtifactRef` fields.

- [x] **Step 2: Run JSON artifact test to verify it fails**

Run: `pytest tests/test_artifact_store.py::test_artifact_store_writes_json_artifact_with_relative_ref -q`

Expected: FAIL because `ArtifactStore` is not implemented/exported.

- [x] **Step 3: Implement JSON artifact writing**

Implement `ArtifactStore.__init__(run_dir)`, directory mapping for `ui_tree`, filename normalization, `write_json(...)`, and `EvidenceArtifactRef` creation with relative path and `mime_type="application/json"`.

- [x] **Step 4: Run JSON artifact test to verify it passes**

Run: `pytest tests/test_artifact_store.py::test_artifact_store_writes_json_artifact_with_relative_ref -q`

Expected: PASS.

### Task 2: Text And Bytes Artifact Writing

**Files:**
- Modify: `tests/test_artifact_store.py`
- Modify: `fsq_agent/core/evidence/_artifact_store.py`

- [x] **Step 1: Write failing text/bytes artifact tests**

Add tests for `write_text(kind="log", ...)` and `write_bytes(kind="screenshot", ...)`. Assert logs go under `artifacts/logs/*.txt`, screenshots go under `artifacts/screenshots/*.png`, and both refs are relative to `run_dir`.

- [x] **Step 2: Run text/bytes tests to verify they fail**

Run: `pytest tests/test_artifact_store.py -q`

Expected: FAIL until `write_text` and `write_bytes` are implemented.

- [x] **Step 3: Implement text and bytes artifact writing**

Implement `write_text(...)` and `write_bytes(...)` with default extensions/mime types by artifact kind. Support `screenshot`, `ui_tree`, `tool_call`, `log`, `json`, `text`, and `other` directory mapping.

- [x] **Step 4: Run artifact store tests to verify they pass**

Run: `pytest tests/test_artifact_store.py -q`

Expected: PASS.

### Task 3: Verification And Commit

**Files:**
- Verify: touched code, tests, and spec

- [x] **Step 1: Run evidence tests**

Run: `pytest tests/test_artifact_store.py tests/test_evidence_recorder.py -q`

Expected: PASS.

- [x] **Step 2: Run full test suite**

Run: `pytest -q`

Expected: PASS.

- [x] **Step 3: Run lint and whitespace checks**

Run: `python3 -m ruff check fsq_agent/core tests/test_artifact_store.py` and `git diff --check`.

Expected: both pass.

- [ ] **Step 4: Commit implementation**

Run: `git add fsq_agent/core/SPEC.md fsq_agent/core/__init__.py fsq_agent/core/evidence/__init__.py fsq_agent/core/evidence/_artifact_store.py tests/test_artifact_store.py docs/superpowers/plans/2026-06-09-artifact-store.md && git commit -m "feat: add evidence artifact store"`
