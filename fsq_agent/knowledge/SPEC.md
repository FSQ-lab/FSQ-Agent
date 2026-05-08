# Module: knowledge

## Purpose

Load private testing knowledge, historical UI elements, application-specific notes, and reusable flow templates. Provide relevant knowledge context to the OpenAI Agents SDK agent without coupling the agent runtime to storage layout.

## Dependencies

- `models`: Uses `Task`, `KnowledgeBundle`, and shared exception types when knowledge loading fails.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `PrivateKnowledgeLoader`: Loads task-referenced knowledge from configured knowledge directories.
- `FlowTemplateManager`: Loads and matches reusable flow templates for common test actions.
- `KnowledgeBundle`: Re-exported shared model from `models` for callers that work through the knowledge module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Knowledge file discovery and loading.
- `_flow_template.py`: Flow template parsing and matching.
- `_bundle.py`: Knowledge aggregation helpers.
- `SPEC.md`: Module design.

## Error Handling

Missing optional knowledge references are recorded as agent context warnings. Invalid required knowledge files raise `FsqAgentError` subclasses from `models` with the failing path and reference name.

## Design Decisions

- Knowledge and flow templates are advisory context, not executable authority.
- Flow templates improve planning speed and element location success but must still be verified at runtime.
- Knowledge storage stays outside the package under top-level `knowledge/` so teams can version app-specific data separately from code.
- Skill loading is owned by the separate `skills` module so private knowledge and reusable automation skills can evolve independently.
