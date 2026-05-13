# Module: skills

## Purpose

Load configured automation skills from local Markdown files, directories, or inline descriptive bundles. Provide skill instructions and file metadata to the OpenAI Agents SDK runtime and optional ShellTool integration without coupling skill loading to private knowledge storage.

## Dependencies

- `models`: Uses `SkillConfig`, `SkillBundle`, and shared exception types when required skill files are missing or invalid.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `SkillLoader`: Loads configured automation skills from Markdown files, directories, or inline descriptive bundles.
- `SkillBundle`: Re-exported shared model from `models` for callers that work through the skills module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Skill discovery, Markdown rendering, and inline bundle loading.
- `SPEC.md`: Module design.

## Error Handling

Missing optional skill references are returned as skill warnings. Invalid or missing required skill files raise `FsqAgentError` subclasses from `models` with the failing path and skill name. Inline skill bundles are accepted as descriptive instructions and do not imply shell execution authority.

## Design Decisions

- Skills are advisory context, not executable authority.
- Local Markdown skills are rendered into instructions/context.
- MCP-specific skills should describe scope, tool selection, argument rules, tool usage error recovery, semantic fidelity rules, and evidence rules. They guide the generic agent for the configured runtime without turning the agent runtime into an MCP-specific implementation.
- When shell execution is enabled, file-backed skills can be attached to the SDK `ShellTool` local environment as descriptive skill metadata; commands still execute only through configured CLI tools or shell policy.
- Skill models remain centralized in `models` so runtime, tools, and configuration share the same serializable contracts.
