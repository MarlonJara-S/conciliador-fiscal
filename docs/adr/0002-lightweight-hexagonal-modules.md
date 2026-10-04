# ADR 0002: Lightweight hexagonal architecture inside each module

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

[ADR 0001](0001-modular-monolith.md) splits P1 into modules (`ingestion`, `invoices`, `storage`, `api`, and later `banking`, `reconciliation`, `radian`, `assistant`). It does not say how code is organized *inside* a module.

The most important rules of the system are business rules: parsing and validating invoices, computing taxes and withholdings, matching payments, counting business days for DIAN deadlines. They must be correct and heavily tested.

At the same time, the system talks to many external things that change or fail: an IMAP mailbox, PostgreSQL, Redis queues, the DIAN, LLM providers, and soon manual uploads. Known upcoming changes already affect these edges: invoices will also arrive by manual upload, and storage will add partitioning and Row-Level Security.

Constraints: one developer with about 8–9 hours per week, so the structure must stay small and must not slow down simple changes.

## Decision

Inside each module, separate code into three layers, with dependencies pointing inward only:

| Layer | Contains | May depend on |
|---|---|---|
| `domain` | Pure business rules: invoice models, parsing XML bytes into an invoice, tax and validation rules | Standard library, Pydantic, `lxml`. **No I/O**: no network, files, database, environment variables or current time (dates are passed in) |
| `application` | Use cases that coordinate a task ("process this document") | `domain`, and ports: small `Protocol` interfaces such as "a place to store invoices" |
| `adapters` | Code that talks to the outside world: PostgreSQL, IMAP, HTTP endpoints, LLM clients | `application` and `domain`; implements the ports |

Rules that keep it lightweight:

- **Ports only at real boundaries.** A `Protocol` is created only where the code talks to something external. No interfaces "just in case".
- **Start small.** A module begins as a few files and is split into the three folders when it grows. The dependency direction applies from day one.
- **Money is `Decimal`, never `float`;** constants are named (no magic numbers).

## Alternatives considered

**Framework-centric code (endpoints and database models hold the logic).** Rejected. It is the fastest way to start with FastAPI and SQLAlchemy, but business rules end up inside HTTP handlers and ORM models. Testing a tax rule would then require a database, and adding manual upload or a new storage strategy would mean editing the rules themselves.

**Full Clean Architecture with tactical DDD** (entities, value objects, aggregates, repositories, domain events, mapping DTOs between every layer). Rejected for now. It adds a lot of ceremony for one developer and a v0 whose domain is still being discovered. Individual patterns (for example a repository port for invoices) are adopted when a concrete need appears.

**No explicit structure; decide case by case.** Rejected. Without a stated rule, I/O leaks into business logic gradually and is expensive to untangle later.

## Consequences

**Positive**

- Business rules are tested in milliseconds, with no database, mailbox or network.
- A new channel (manual upload) or a storage change only adds or replaces an adapter.
- The design answers the common interview question "what happens if we change the database?" with real code.

**Negative and risks**

- More files and some indirection than a flat module.
- Risk of over-engineering by creating ports with a single trivial implementation. Mitigation: the "ports only at real boundaries" rule, checked in code review.
- Passing the current date into the domain instead of reading the clock is less natural at first, but makes deadline rules testable.

**How we will know it was a good decision**

- `domain` packages import nothing from `adapters` or from infrastructure libraries (database drivers, HTTP clients). This will be enforced with an import-boundary check in CI (for example `import-linter`).
- Domain tests run without any external service and the whole domain test suite takes a few seconds.
- Adding manual upload in a later version requires no changes to `invoices/domain`.
