# Module: skills

## Purpose

Load configured automation skills from local Markdown files, directories, or inline descriptive bundles. Provide only complete skill instructions and file metadata to the OpenAI Agents SDK runtime without coupling skill loading to private knowledge storage or granting command execution authority.

## Dependencies

- `models`: Uses `SkillConfig`, `SkillBundle`, and shared exception types when required skill files are missing or invalid.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `SkillLoader`: Loads configured automation skills from Markdown files, directories, or inline descriptive bundles. Required broken skills fail fast; optional broken skills are skipped with operator-visible diagnostics and are not returned as model-facing bundles.
- `SkillBundle`: Re-exported shared model from `models` for callers that work through the skills module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Skill discovery, Markdown rendering, and inline bundle loading.
- `SPEC.md`: Module design.

## Error Handling

Invalid or missing required skill files raise `FsqAgentError` subclasses from `models` with the failing path and skill name. Optional skill entries with missing paths, missing files, unreadable files, invalid directories, or no inline content are skipped and logged as diagnostics. Skipped optional skills must not be returned as warning-only `SkillBundle` values or sent to LLM prompts. Inline skill bundles are accepted as descriptive instructions and do not imply shell execution authority.

## Design Decisions

- Skills are advisory context, not executable authority.
- Local Markdown skills are rendered into instructions/context only when successfully loaded.
- Harness- or platform-specific skills should describe scope, action selection, argument rules, tool usage error recovery, semantic fidelity rules, and evidence rules. They guide the generic agent for the configured runtime without turning the agent runtime into a platform-specific implementation.
- Skills do not attach command execution tools. Any future command capability requires its own SPEC update outside the skills module.
- Skill models remain centralized in `models` so runtime, tools, and configuration share the same serializable contracts.
- Skill loader diagnostics are operational metadata for logs or runtime events, not prompt content. The LLM should see complete skill instructions or no skill block.
