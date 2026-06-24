# Python Implementation Rules

## Public API

- Export public symbols from `__init__.py` or the documented entry point.
- Keep public names intentional and stable.
- Do not make a helper public because another module wants to bypass the owner module.

## Imports

- Project imports must follow the dependency direction in root/module SPEC.
- Avoid cycles. If two modules need each other, extract a shared abstraction or move ownership.
- Do not import `_private` files from another module.

## Framework Boundaries

- FastAPI routers, Django views, Flask routes, CLI commands, and worker handlers should parse/validate input and call application/domain code.
- Do not bury core business rules in route handlers, serializers, management commands, or task callbacks.
- Domain/application code should be testable without booting the framework.

## Model Boundaries

- Pydantic models validate and serialize boundary data by default.
- ORM models represent persistence by default.
- Domain objects represent business rules by default.
- Combining these roles is acceptable only for simple modules and must be stated in SPEC.

## Services, Repositories, and Unit of Work

- Use an application service when a use case coordinates multiple objects, dependencies, or side effects.
- Use a repository when it hides meaningful persistence complexity or protects dependency direction.
- Use Unit of Work when transaction consistency spans multiple persistence operations.
- Avoid empty pass-through layers.

## Tests

- Test public behavior, not private implementation details.
- Put domain invariants under fast unit tests.
- Put database/framework integrations under explicit integration tests.
- For refactoring, add characterization tests before changing behavior when coverage is weak.

## Anti-Patterns

- `services/` full of functions that only call one repository method.
- `models.py` containing ORM, API schemas, and domain behavior with no stated reason.
- Routers/views containing business invariants.
- Repository introduced for every table by default.
- Module SPEC says one dependency direction while imports do another.
