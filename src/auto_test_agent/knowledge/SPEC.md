# Module: knowledge

## Purpose

Load private testing knowledge, historical UI elements, application-specific notes, reusable flow templates, and automation skills. Provide relevant context to the OpenAI Agents SDK agent without coupling the agent runtime to storage layout.

## Dependencies

- `models`: Uses `Task`, `KnowledgeBundle`, `SkillConfig`, `SkillBundle`, and shared exception types when knowledge or skill loading fails.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `PrivateKnowledgeLoader`: Loads task-referenced knowledge from configured knowledge directories.
- `FlowTemplateManager`: Loads and matches reusable flow templates for common test actions.
- `SkillLoader`: Loads configured automation skills from local Markdown files, directories, or inline descriptive bundles.
- `KnowledgeBundle`: Re-exported shared model from `models` for callers that work through the knowledge module.
- `SkillBundle`: Re-exported shared model from `models` for callers that work through the knowledge module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Knowledge file discovery and loading.
- `_flow_template.py`: Flow template parsing and matching.
- `_skill_loader.py`: Skill discovery, Markdown rendering, and inline bundle loading.
- `_bundle.py`: Knowledge aggregation helpers.
- `SPEC.md`: Module design.

## Error Handling

Missing optional knowledge or skill references are recorded as agent context warnings. Invalid required knowledge or skill files raise `AutoTestAgentError` subclasses from `models` with the failing path and reference name. Inline skill bundles are accepted as descriptive instructions and do not imply shell execution authority.

## Design Decisions

- Knowledge and skills are advisory context, not executable authority.
- Flow templates improve planning speed and element location success but must still be verified at runtime.
- Knowledge storage stays outside the package under top-level `knowledge/` so teams can version app-specific data separately from code.
- Local Markdown skills are rendered into instructions/context. When shell execution is enabled, file-backed skills are also attached to the SDK `ShellTool` local environment as descriptive skill metadata; commands still execute only through configured CLI tools or shell policy.
