# Python Architecture Levels

Use the lowest level that keeps behavior clear, testable, and changeable.

## Level 1: Script

Use for one-off automation, migration helpers, small data transforms, and local tools.

Allowed shape:

```text
script.py
```

Rules:

- Keep functions small and named by intent.
- Avoid framework or package scaffolding.
- Add tests only when the script is reused, risky, or business critical.

Escalate when the script gains users, repeated changes, shared logic, or stateful behavior.

## Level 2: Simple Package

Use for small libraries, utilities, and focused modules.

Allowed shape:

```text
package/
  __init__.py
  core.py
  _helpers.py
tests/
```

Rules:

- Public functions/classes are exported from `__init__.py`.
- Internal helpers stay private.
- Avoid service/repository layers unless there is real orchestration or persistence complexity.

## Level 3: Layered Application

Use for APIs, CLIs, workers, and apps with orchestration plus external dependencies.

Typical shape:

```text
app/
  api/ or cli/
  services/
  models/
  persistence/
  integrations/
```

Rules:

- Transport layer handles HTTP/CLI/message details.
- Services orchestrate use cases.
- Persistence and integrations are behind narrow interfaces when tests or change isolation need it.

Avoid if layers only pass parameters through unchanged.

## Level 4: Clean Architecture

Use when business rules must remain independent from frameworks, databases, UI, or external services.

Typical shape:

```text
module/
  domain/
  application/
  infrastructure/
  interface/
```

Rules:

- Dependencies point inward.
- Domain has no framework/database imports.
- Application coordinates use cases through ports/protocols.
- Infrastructure implements ports.

Avoid for simple CRUD where framework-native structure is clearer.

## Level 5: Light DDD

Use when the domain has rich behavior, invariants, policies, lifecycle rules, or distinct bounded contexts.

Typical concepts:

- Entity
- Value Object
- Aggregate
- Repository
- Domain Service
- Domain Event
- Bounded Context

Rules:

- Model business language directly.
- Put invariants in domain objects, not controllers or serializers.
- Use repositories for aggregate persistence, not generic table access.
- Keep DDD tactical patterns light; do not create ceremony without business complexity.

Avoid when the system is mostly CRUD, reporting, or data movement.
