# FSQ-Agent v2 Phase 0 Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the approved FSQ-Agent v2 architecture into module-level specs and explicit contracts before any product code implementation.

**Architecture:** Phase 0 is documentation and contract design only. It updates repository specs so later Android regression-runner work can add code against agreed contracts for action IR, execution core, harness adapters, evidence bundles, verifiers, debug artifacts, and knowledge write-back.

**Tech Stack:** Markdown specs, Mermaid diagrams, existing Python package structure under `fsq_agent/`, pytest only for repository sanity checks.

**Language Policy:** English is the contract source of truth. Each new or materially changed design/spec document must include a Chinese reading companion in the same file or an adjacent `*.zh.md` file referenced from the English file.

---

## Scope / 范围

English: This plan implements Phase 0 from `docs/superpowers/specs/2026-06-04-fsq-agent-v2-architecture-design.md`. It does not add runtime code, CLI commands, model calls, Appium calls, or report generation behavior.

中文：本计划实现架构 spec 中的 Phase 0。它不新增运行时代码、CLI 命令、模型调用、Appium 调用或报告生成行为。

## File Structure / 文件结构

- Modify: `CLAUDE.md`
  - Add the v2 architecture spec as an upstream reference.
  - Add the bilingual documentation rule.
- Modify: `fsq_agent/models/SPEC.md`
  - Define shared v2 contract families at the spec level: action IR, execution result, evidence bundle, harness capability, verifier decision, debug artifact, knowledge write-back.
- Modify: `fsq_agent/fsq/SPEC.md`
  - Split current advisory FSQ behavior from future deterministic runner behavior.
  - Define the first regression-runner command set for Android MVP.
- Modify: `fsq_agent/tools/SPEC.md`
  - Define how existing MCP/lifecycle/tool capabilities evolve into harness adapters.
  - Keep current OpenAI Agents SDK tool behavior intact until implementation tasks change code.
- Modify: `fsq_agent/agent/SPEC.md`
  - Clarify current agent loop versus v2 planner loop.
  - State that natural-goal planning targets generated FSQ YAML and uses shared execution contracts.
- Modify: `fsq_agent/report/SPEC.md`
  - Add evidence bundle and debug artifact contract expectations.
- Modify: `fsq_agent/knowledge/SPEC.md`
  - Add reviewed write-back design and knowledge categories.
- Create: `docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md`
  - Central bilingual contract document for action IR, harness, evidence, verifier, debug, and knowledge write-back.

## Task 1: Repository Architecture Guide

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update repository guide with v2 reference and bilingual rule**

Edit `CLAUDE.md` to add this section after the opening spec-driven development paragraph:

```markdown
## FSQ-Agent v2 Architecture Reference

`docs/superpowers/specs/2026-06-04-fsq-agent-v2-architecture-design.md` is the upstream architecture design for FSQ-Agent v2. It defines the target Dual Loop, Shared Harness direction, but it does not directly authorize product-code changes.

Implementation work derived from v2 must update and confirm the relevant module-level `SPEC.md` files before code changes.

## Documentation Language Policy

Architecture, plan, and module design documents created for FSQ-Agent v2 must be bilingual. English is the contract source of truth. Chinese is the reading companion and must be updated in the same change when the English contract changes.
```

- [ ] **Step 2: Verify the guide contains both new headings**

Run:

```bash
rg -n "FSQ-Agent v2 Architecture Reference|Documentation Language Policy" CLAUDE.md
```

Expected: two matches, one for each heading.

- [ ] **Step 3: Commit Task 1**

```bash
git add CLAUDE.md
git commit -m "docs: reference FSQ-Agent v2 architecture guide"
```

## Task 2: Core Contracts Spec

**Files:**
- Create: `docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md`

- [ ] **Step 1: Create the bilingual core contracts spec**

Create `docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md` with this content:

```markdown
# FSQ-Agent v2 Core Contracts Spec

Status: draft for review
Date: 2026-06-04
Scope: contract design for Phase 0, no runtime implementation
Language policy: English is the contract source of truth. The Chinese section is a reading companion and must be updated with English contract changes.

## 1. Purpose

This spec defines the core contracts that connect FSQ YAML execution, natural-goal planning, platform harnesses, evidence collection, verification, debug artifacts, reports, and knowledge write-back.

## 2. Action IR

Action IR is the normalized representation of executable UI test intent. It is produced from FSQ YAML or planner output and consumed by the shared execution core.

Required fields:

- `action_id`: stable per-case action identifier.
- `source`: `fsq_yaml`, `planner_generated`, or `repair_generated`.
- `kind`: normalized action kind such as `tap`, `type_text`, `press_key`, `wait`, `scroll`, `swipe`, `assert_visible`, `assert_text`, `assert_ai`, `launch_app`, or `close_app`.
- `target`: optional structured target with locator, text, role, coordinates, or platform-specific hint.
- `input`: optional action input such as text, key name, duration, or assertion prompt.
- `timeout_ms`: action-level timeout.
- `required`: whether failure blocks case success.
- `metadata`: non-authoritative source metadata for debugging and traceability.

## 3. Harness Adapter Contract

A harness adapter executes normalized actions and returns observations. Platform-specific APIs remain behind the adapter.

Required capabilities:

- Report static capability metadata before execution.
- Own platform lifecycle setup and teardown hooks.
- Execute one Action IR at a time.
- Capture or reference screenshots when supported.
- Capture or reference UI tree snapshots when supported.
- Return structured action results with artifact paths.
- Classify platform failures as lifecycle, action, observation, timeout, or unsupported capability.

## 4. Evidence Bundle

The evidence bundle is the authoritative execution record shared by reports, verifiers, debug UI, and knowledge write-back.

Required top-level sections:

- `run`: run id, case id, platform, timestamps, environment summary.
- `actions`: ordered action records with inputs, outputs, status, timing, and artifact references.
- `observations`: screenshots, UI trees, page sources, device state, or browser state.
- `assertions`: deterministic and model-assisted assertion records.
- `tool_logs`: normalized MCP, CLI, harness, and lifecycle call records.
- `verifier`: step-level and case-level verifier decisions.
- `debug`: paths to generated debug artifacts.

## 5. Verifier Contracts

Step verifier decisions are deterministic and close to execution. Case verifier decisions judge the whole case from the evidence bundle.

Decision statuses:

- `passed`
- `failed`
- `inconclusive`
- `skipped`

Each decision must include:

- `decision_id`
- `scope`: `step` or `case`
- `status`
- `reason`
- `evidence_refs`
- `blocking`

## 6. Debug Artifact Contract

The debug system must read the same evidence bundle used by verification. The first implementation target is a static HTML artifact with embedded metadata and relative links to evidence files.

Minimum views:

- timeline
- screenshots
- UI tree snapshots
- tool logs
- assertion evidence
- verifier decisions
- failure summary

## 7. Knowledge Write-Back Contract

Knowledge write-back stores reviewed testing experience. Automatic writes must be marked as unreviewed until a later review workflow promotes them.

Knowledge categories:

- page graph
- element memory
- successful action sequence
- failure pattern
- repair recipe
- platform note
- planner lesson

Every write-back record must include source run id, evidence references, confidence, review status, and timestamp.

---

# FSQ-Agent v2 核心契约 Spec 中文阅读版

状态：待评审草案
日期：2026-06-04
范围：Phase 0 契约设计，不包含运行时实现
语言策略：英文部分是契约级事实来源。中文部分用于阅读辅助，并应随英文契约变化同步更新。

## 1. 目的

本 spec 定义连接 FSQ YAML 执行、natural-goal planning、平台 harness、evidence collection、verification、debug artifacts、reports 和 knowledge write-back 的核心契约。

## 2. Action IR

Action IR 是可执行 UI 测试意图的规范化表示。它由 FSQ YAML 或 planner output 生成，并由 shared execution core 消费。

必须包含的字段：`action_id`、`source`、`kind`、`target`、`input`、`timeout_ms`、`required`、`metadata`。

## 3. Harness Adapter Contract

Harness adapter 负责执行 normalized actions 并返回 observations。平台 API 细节留在 adapter 内部。

必须支持：capability metadata、lifecycle setup/teardown、单步 Action IR 执行、screenshot/UI tree 引用、structured action result、failure classification。

## 4. Evidence Bundle

Evidence bundle 是 report、verifier、debug UI 和 knowledge write-back 共享的权威执行记录。

顶层 section 包括：`run`、`actions`、`observations`、`assertions`、`tool_logs`、`verifier`、`debug`。

## 5. Verifier Contracts

Step verifier 靠近执行点做确定性判断。Case verifier 基于 evidence bundle 判断整个 case。

Decision status 包括：`passed`、`failed`、`inconclusive`、`skipped`。

每个 decision 必须包含：`decision_id`、`scope`、`status`、`reason`、`evidence_refs`、`blocking`。

## 6. Debug Artifact Contract

Debug system 必须读取 verifier 使用的同一份 evidence bundle。第一阶段目标是 static HTML artifact，包含 metadata 和指向 evidence files 的相对链接。

最小视图包括：timeline、screenshots、UI tree snapshots、tool logs、assertion evidence、verifier decisions、failure summary。

## 7. Knowledge Write-Back Contract

Knowledge write-back 保存经过 review 的测试经验。自动写入必须标记为 unreviewed，直到后续 review workflow 提升它。

知识类别包括：page graph、element memory、successful action sequence、failure pattern、repair recipe、platform note、planner lesson。

每条 write-back record 必须包含 source run id、evidence references、confidence、review status 和 timestamp。
```

- [ ] **Step 2: Verify the core contracts spec has English and Chinese sections**

Run:

```bash
rg -n "Core Contracts Spec|核心契约 Spec 中文阅读版|Action IR|Evidence Bundle" docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md
```

Expected: matches for both English and Chinese headings plus contract sections.

- [ ] **Step 3: Commit Task 2**

```bash
git add docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md
git commit -m "docs: define FSQ-Agent v2 core contracts"
```

## Task 3: Models Module Spec Update

**Files:**
- Modify: `fsq_agent/models/SPEC.md`

- [ ] **Step 1: Add v2 contract ownership to models spec**

In `fsq_agent/models/SPEC.md`, add this design decision under `## Design Decisions`:

```markdown
- FSQ-Agent v2 shared contracts will be owned by `models` before implementation code is added. The planned contract families are Action IR, harness capability metadata, harness action result, evidence bundle, observation reference, assertion record, verifier decision, debug artifact reference, and knowledge write-back record. Detailed field-level contracts are defined in `docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md` and must be reflected here before Python model classes are created.
- V2 contract models must remain provider-neutral and platform-neutral. Provider-specific fields belong in metadata or provider-specific adapter models, not in the shared contract surface.
- V2 evidence models must use artifact references rather than embedding large screenshot, UI tree, or tool-output payloads directly in shared result objects.
```

Add this Chinese companion immediately after it:

```markdown
中文阅读版：

- FSQ-Agent v2 的共享契约在实现前应先由 `models` 模块承担 spec 层面的 ownership。计划中的契约族包括 Action IR、harness capability metadata、harness action result、evidence bundle、observation reference、assertion record、verifier decision、debug artifact reference、knowledge write-back record。字段级契约定义在 `docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md`，创建 Python model class 前必须同步反映到本模块 spec。
- V2 契约模型必须保持 provider-neutral 和 platform-neutral。Provider-specific 字段应放在 metadata 或 provider-specific adapter model 中，而不是共享契约表面。
- V2 evidence model 必须使用 artifact reference，不应在共享 result object 中直接嵌入大体积 screenshot、UI tree 或 tool-output payload。
```

- [ ] **Step 2: Verify models spec references the core contracts document**

Run:

```bash
rg -n "v2 shared contracts|核心契约|2026-06-04-fsq-agent-v2-core-contracts" fsq_agent/models/SPEC.md
```

Expected: at least three matches.

- [ ] **Step 3: Commit Task 3**

```bash
git add fsq_agent/models/SPEC.md
git commit -m "docs: map v2 contracts to models spec"
```

## Task 4: FSQ Module Spec Update

**Files:**
- Modify: `fsq_agent/fsq/SPEC.md`

- [ ] **Step 1: Add deterministic runner direction**

In `fsq_agent/fsq/SPEC.md`, add this section before `## Error Handling`:

```markdown
## V2 Regression Runner Direction

The current FSQ module treats FSQ YAML as structured context for the agent loop. FSQ-Agent v2 adds a separate deterministic regression-runner path. The existing advisory adapter must remain valid until implementation work explicitly replaces or complements it.

The deterministic runner path will:

- validate `.codex.yaml` before execution;
- normalize executable commands into Action IR;
- preserve source metadata for traceability;
- reject unsupported required commands before execution;
- execute without requiring a planner model;
- emit action records and assertion records for the evidence bundle.

The first Android MVP command set is:

- app lifecycle intent: `launchApp`, `killApp`;
- interaction: `tap`, `input`, `pressKey`, `scroll`, `swipe`, `wait`;
- deterministic assertions: `assert`, `assertVisible`;
- model-assisted visual assertion bridge: `assertWithAI`, represented as an assertion action with screenshot evidence binding.

中文阅读版：

当前 FSQ 模块把 FSQ YAML 作为 agent loop 的结构化上下文。FSQ-Agent v2 会增加独立的 deterministic regression-runner path。现有 advisory adapter 在后续实现明确替换或补充前必须保持有效。

Deterministic runner path 将负责：执行前 validation、把 executable commands 规范化为 Action IR、保留 source metadata、执行前拒绝 unsupported required commands、不依赖 planner model 执行、为 evidence bundle 产生 action record 和 assertion record。

Android MVP 第一批 command set 包括：`launchApp`、`killApp`、`tap`、`input`、`pressKey`、`scroll`、`swipe`、`wait`、`assert`、`assertVisible`、`assertWithAI`。
```

- [ ] **Step 2: Verify FSQ spec contains the MVP command set**

Run:

```bash
rg -n "V2 Regression Runner Direction|Android MVP command set|assertWithAI|中文阅读版" fsq_agent/fsq/SPEC.md
```

Expected: matches for the new section and command set.

- [ ] **Step 3: Commit Task 4**

```bash
git add fsq_agent/fsq/SPEC.md
git commit -m "docs: specify v2 FSQ regression runner direction"
```

## Task 5: Harness and Tools Spec Update

**Files:**
- Modify: `fsq_agent/tools/SPEC.md`

- [ ] **Step 1: Add harness adapter direction**

In `fsq_agent/tools/SPEC.md`, add this section before `## Error Handling`:

```markdown
## V2 Harness Adapter Direction

The current tools module exposes MCP, CLI, file, shell, and lifecycle capabilities to the OpenAI Agents SDK runtime. FSQ-Agent v2 introduces a harness adapter contract above those concrete capabilities.

The harness adapter contract will not remove MCP or lifecycle controllers. It will organize them behind platform-oriented execution semantics:

- capability discovery;
- setup and teardown;
- single Action IR execution;
- observation capture or artifact reference;
- structured failure classification;
- evidence bundle record creation.

For Android MVP, the harness may use Appium MCP, direct Appium calls, or a hybrid adapter. The module-level implementation spec must choose one before code changes.

中文阅读版：

当前 tools 模块把 MCP、CLI、file、shell 和 lifecycle capabilities 暴露给 OpenAI Agents SDK runtime。FSQ-Agent v2 会在这些具体能力之上引入 harness adapter contract。

Harness adapter contract 不会移除 MCP 或 lifecycle controllers，而是把它们组织成平台导向的执行语义：capability discovery、setup/teardown、单步 Action IR execution、observation capture 或 artifact reference、structured failure classification、evidence bundle record creation。

Android MVP 可以使用 Appium MCP、direct Appium calls 或 hybrid adapter。代码修改前，模块级 implementation spec 必须选定一种方案。
```

- [ ] **Step 2: Verify tools spec contains harness direction**

Run:

```bash
rg -n "V2 Harness Adapter Direction|capability discovery|Android MVP|中文阅读版" fsq_agent/tools/SPEC.md
```

Expected: matches for the new section and Android decision note.

- [ ] **Step 3: Commit Task 5**

```bash
git add fsq_agent/tools/SPEC.md
git commit -m "docs: specify v2 harness adapter direction"
```

## Task 6: Agent Planner Spec Update

**Files:**
- Modify: `fsq_agent/agent/SPEC.md`

- [ ] **Step 1: Add v2 planner-loop direction**

In `fsq_agent/agent/SPEC.md`, add this section before `## Error Handling`:

```markdown
## V2 Planner Loop Direction

The current agent module owns OpenAI Agents SDK orchestration, pre-planning, execution, verification, retry, and report generation. FSQ-Agent v2 separates two concerns that are currently close together:

- natural-goal planning and testcase generation;
- deterministic FSQ YAML regression execution.

The v2 planner loop should target FSQ YAML or structured testcase drafts as durable output. When it needs live UI validation, it must call the shared execution core rather than bypassing the harness contract.

The planner loop must be model-provider neutral. OpenAI and GitHub Copilot are required target providers, but provider-specific authentication and request details must not leak into planner decisions.

中文阅读版：

当前 agent 模块负责 OpenAI Agents SDK orchestration、pre-planning、execution、verification、retry 和 report generation。FSQ-Agent v2 会把 natural-goal planning/testcase generation 与 deterministic FSQ YAML regression execution 拆开。

V2 planner loop 应以 FSQ YAML 或 structured testcase draft 作为持久输出。需要 live UI validation 时，必须调用 shared execution core，不能绕过 harness contract。

Planner loop 必须 model-provider neutral。OpenAI 和 GitHub Copilot 是必需目标 provider，但 provider-specific 认证和请求细节不能泄漏到 planner decision 中。
```

- [ ] **Step 2: Verify agent spec contains planner direction**

Run:

```bash
rg -n "V2 Planner Loop Direction|model-provider neutral|structured testcase draft|中文阅读版" fsq_agent/agent/SPEC.md
```

Expected: matches for the new section.

- [ ] **Step 3: Commit Task 6**

```bash
git add fsq_agent/agent/SPEC.md
git commit -m "docs: specify v2 planner loop direction"
```

## Task 7: Report, Debug, and Knowledge Specs

**Files:**
- Modify: `fsq_agent/report/SPEC.md`
- Modify: `fsq_agent/knowledge/SPEC.md`

- [ ] **Step 1: Add evidence/debug direction to report spec**

In `fsq_agent/report/SPEC.md`, add this section before `## Error Handling`:

```markdown
## V2 Evidence and Debug Direction

FSQ-Agent v2 reports must be generated from the same evidence bundle used by verification. Markdown and JSON reports remain useful, but debug artifacts become first-class outputs.

The first debug artifact target is static HTML with relative links to evidence files. It must include timeline, screenshots, UI tree snapshots, tool logs, assertion evidence, verifier decisions, and failure summary.

中文阅读版：

FSQ-Agent v2 report 必须从 verifier 使用的同一份 evidence bundle 生成。Markdown 和 JSON report 继续保留，但 debug artifacts 成为一等输出。

第一阶段 debug artifact 目标是 static HTML，并使用相对路径链接 evidence files。它必须包含 timeline、screenshots、UI tree snapshots、tool logs、assertion evidence、verifier decisions 和 failure summary。
```

- [ ] **Step 2: Add write-back direction to knowledge spec**

In `fsq_agent/knowledge/SPEC.md`, add this section before `## Error Handling`:

```markdown
## V2 Knowledge Write-Back Direction

The current knowledge module loads advisory context. FSQ-Agent v2 extends knowledge into reviewed testing experience accumulated from runs.

Knowledge write-back categories are page graph, element memory, successful action sequence, failure pattern, repair recipe, platform note, and planner lesson. Automatically generated write-back records must be marked unreviewed until a review workflow promotes them.

中文阅读版：

当前 knowledge 模块加载 advisory context。FSQ-Agent v2 会把 knowledge 扩展为从 run 中积累、经过 review 的测试经验。

Knowledge write-back 分类包括 page graph、element memory、successful action sequence、failure pattern、repair recipe、platform note、planner lesson。自动生成的 write-back record 必须标记为 unreviewed，直到 review workflow 提升它。
```

- [ ] **Step 3: Verify report and knowledge specs contain v2 direction**

Run:

```bash
rg -n "V2 Evidence and Debug Direction|static HTML|V2 Knowledge Write-Back Direction|unreviewed" fsq_agent/report/SPEC.md fsq_agent/knowledge/SPEC.md
```

Expected: matches in both files.

- [ ] **Step 4: Commit Task 7**

```bash
git add fsq_agent/report/SPEC.md fsq_agent/knowledge/SPEC.md
git commit -m "docs: specify v2 report debug and knowledge direction"
```

## Task 8: Final Phase 0 Review

**Files:**
- Read: `CLAUDE.md`
- Read: `docs/superpowers/specs/2026-06-04-fsq-agent-v2-architecture-design.md`
- Read: `docs/superpowers/specs/2026-06-04-fsq-agent-v2-core-contracts.md`
- Read: `fsq_agent/models/SPEC.md`
- Read: `fsq_agent/fsq/SPEC.md`
- Read: `fsq_agent/tools/SPEC.md`
- Read: `fsq_agent/agent/SPEC.md`
- Read: `fsq_agent/report/SPEC.md`
- Read: `fsq_agent/knowledge/SPEC.md`

- [ ] **Step 1: Run placeholder scan across updated docs**

Run:

```bash
rg -n "TBD|TODO|FIXME" CLAUDE.md docs/superpowers/specs fsq_agent/*/SPEC.md
```

Expected: no matches introduced by Phase 0 work. Existing unrelated matches, if any, must be reported with file and line.

- [ ] **Step 2: Run repository tests as a sanity check**

Run:

```bash
pytest
```

Expected: existing test suite passes. If tests fail, inspect whether failures are caused by documentation-only changes. Documentation-only Phase 0 should not change runtime behavior.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: no tracked changes left. `docs/.DS_Store` may remain untracked and should not be committed.

- [ ] **Step 4: Commit final cleanup only if needed**

If Task 8 finds documentation fixes, commit only those fixes:

```bash
git add CLAUDE.md docs/superpowers/specs fsq_agent/*/SPEC.md
git commit -m "docs: finalize FSQ-Agent v2 phase 0 specs"
```

If no fixes are needed, do not create an empty commit.

---

# 中文阅读版

## 目标

本计划把 FSQ-Agent v2 架构 spec 转换成模块级 spec 和核心契约。Phase 0 不写运行时代码，而是先明确 Action IR、shared execution core、harness adapter、evidence bundle、verifier、debug artifact、knowledge write-back 的边界。

## 执行策略

- 先更新仓库级开发规则，明确 v2 架构文档和双语文档要求。
- 创建核心契约 spec，作为后续 Python model 和模块接口的依据。
- 更新 `models`、`fsq`、`tools`、`agent`、`report`、`knowledge` 的模块级 spec。
- 每个任务单独验证、单独提交，便于 review 和回滚。
- 最后运行占位符扫描、`pytest` 和 `git status`，确认 Phase 0 没有影响运行时代码。

## 非目标

- 不实现 deterministic runner。
- 不新增 CLI workflow。
- 不新增 harness adapter 代码。
- 不生成 HTML debug UI。
- 不修改现有测试逻辑。

## 完成标准

- 架构 spec 和核心 contract spec 都是双语文档。
- 模块级 spec 已说明 v2 方向和后续实现前置条件。
- Phase 1 可以基于这些 spec 继续写 Android regression runner 的实现计划。
