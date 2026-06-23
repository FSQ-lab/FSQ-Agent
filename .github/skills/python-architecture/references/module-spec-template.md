# Python Module SPEC Template

Use this when creating or updating a Python module `SPEC.md`.

```text
# Module: {module_name}

## Purpose
{What this module owns. State what it does not own when boundary confusion is likely.}

## Dependencies
- Internal project dependencies: {allowed module imports}
- External dependencies: {libraries/frameworks}
- Forbidden dependencies: {imports that would violate the architecture}

## Public Interface
- Exports: {symbols exported from __init__.py or public entry point}
- Commands/endpoints/events: {if applicable}
- Stability: {stable, provisional, internal-only}

## Internal Structure
- `{file_or_package}`: {responsibility}
- `_internal.py`: {private responsibility, if applicable}

## Python Architecture
- Architecture level: {1-5 and name}
- Public API: {symbols, commands, endpoints, events, or classes}
- Internal modules: {files not imported outside this module}
- Domain boundaries: {where business rules live}
- Boundary models: {Pydantic schemas, DTOs, ORM models, serializers}
- Dependency direction: {allowed imports and forbidden imports}
- Rationale: {why this level is sufficient}

## Error Handling
{Exceptions, result types, validation behavior, retry/fallback policy, and user-visible errors.}

## Testing Contract
- Unit tests: {public behavior and domain rules}
- Integration tests: {framework/database/external boundaries}
- Regression tests: {known risky cases}
- Verification commands: {pytest/ruff/mypy/pyright/etc.}

## Design Decisions
- {Decision}: {Reason and trade-off}
```

Keep the SPEC concrete. Avoid vague statements such as "handle errors properly" or "use clean code". Name the actual public behavior, dependencies, and boundaries.
