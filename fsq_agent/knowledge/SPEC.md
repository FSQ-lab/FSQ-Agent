# Module: knowledge

## Purpose

Load private testing knowledge, historical UI elements, application-specific notes, plain-text/image knowledge assets, and reusable flow templates. Provide relevant knowledge context to the OpenAI Agents SDK agent without coupling the agent runtime to storage layout or a single upstream data source.

## Dependencies

- `models`: Uses `Task`, `KnowledgeBundle`, and shared exception types when knowledge loading fails.

## Public Interface

Current `__init__.py` exports via `__all__`:

- `KnowledgeProvider`: Protocol for adapters that can supply relevant knowledge for a task.
- `DirectoryKnowledgeProvider`: Default adapter for the configured knowledge directory. It reads global `index.md`, task-referenced text/YAML/JSON files, and discovers image assets for future adapters.
- `PrivateKnowledgeLoader`: Loads task-referenced knowledge from configured knowledge directories.
- `FlowTemplateManager`: Loads and matches reusable flow templates for common test actions.
- `KnowledgeBundle`: Re-exported shared model from `models` for callers that work through the knowledge module.

## Internal Structure

- `__init__.py`: Public exports only.
- `_loader.py`: Knowledge provider protocol, directory-backed provider, file discovery, and loader aggregation.
- `_flow_template.py`: Flow template parsing and matching.
- `_bundle.py`: Knowledge aggregation helpers.
- `SPEC.md`: Module design.

## Error Handling

Missing optional knowledge references are recorded as agent context warnings. Invalid required knowledge files raise `FsqAgentError` subclasses from `models` with the failing path and reference name.

## Design Decisions

- Knowledge and flow templates are advisory context, not executable authority.
- Knowledge loading is provider-based. `PrivateKnowledgeLoader` aggregates one or more `KnowledgeProvider` implementations so future upstreams can supply plain files, generated indexes, image manifests, databases, or service-backed knowledge without changing the agent runtime.
- The default `DirectoryKnowledgeProvider` reads `index.md` automatically when present. `index.md` is the concise global index and project background note for the knowledge directory, and it is included for every task under the key `index.md`.
- Task-specific `Task.knowledge_refs` remain supported and are resolved relative to the configured knowledge directory.
- Plain text and Markdown are loaded as strings. JSON and YAML are parsed into structured values. Image files are discovered as assets for future providers, but this implementation does not attach image pixels to the model prompt.
- Flow templates improve planning speed and element location success but must still be verified at runtime.
- Knowledge storage stays outside the package under top-level `knowledge/` so teams can version app-specific data separately from code.
- Skill loading is owned by the separate `skills` module so private knowledge and reusable automation skills can evolve independently.
