# ADR 0001: Modular monolith instead of microservices

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

P1 ingests electronic invoices (UBL 2.1 XML) received by email, stores them for several client companies, and will later reconcile them against bank statements, track DIAN legal deadlines and answer questions with an AI assistant.

Constraints:

- One developer, with about 8–9 hours per week.
- The domain has clear areas of responsibility: receiving documents, understanding invoices, storing them, and serving them to users. More areas arrive in v1 and v2 (banking, reconciliation, RADIAN deadlines, assistant).
- The core flow needs strong consistency: an invoice must be stored exactly once (unique CUFE per company), even when the same email arrives twice or a worker dies mid-process.
- The system must be cheap to run and simple to deploy while it has few users.

## Decision

Build P1 as a **modular monolith**: one deployable application and one PostgreSQL database, split internally into modules with a single responsibility each.

Modules for v0:

| Module | Responsibility |
|---|---|
| `ingestion` | Receive emails, identify the company, store the original document, skip already-processed messages |
| `invoices` | Unzip, parse XML safely, extract the invoice from the `AttachedDocument`, validate it |
| `storage` | Persist invoices idempotently (one row per CUFE and company) |
| `api` | Expose the data to the accountant and the business owner |

Rules:

- Each piece of data has one owner. Other modules ask the owner for it instead of re-reading or re-parsing it (for example, `reconciliation` reads invoices through `storage`, never by parsing XML).
- Modules talk through explicit public functions, not through each other's internals.

## Alternatives considered

**Microservices (one service per module).** Rejected. Each service would need its own deployment, configuration, monitoring and network calls. Storing an invoice exactly once would require coordination across services (distributed transactions or sagas) for a problem a single database transaction solves. That operational cost is not justified for one developer and a small number of users.

**Traditional monolith without module boundaries.** Rejected. It is the fastest way to start, but parsing, storage and HTTP code mix quickly. A change in the DIAN XML format would then touch many files, and adding reconciliation in v1 would mean changing code that already works.

**Serverless functions (one function per step).** Rejected for now. Local development and testing become harder, cold starts add latency, and the flow would be split across functions before its boundaries are proven. It can be revisited for isolated pieces later, such as an email webhook.

## Consequences

**Positive**

- One deploy, one database, and simple transactions: the "store exactly once" rule is enforced with a unique constraint and `INSERT ... ON CONFLICT`.
- New capabilities (banking, reconciliation, RADIAN, assistant) are added as new modules without rewriting existing ones.
- A module can be extracted into its own service later if it needs independent scaling, because its boundary already exists.

**Negative and risks**

- Boundaries are only a convention inside one codebase and can erode over time. Mitigation: enforce allowed imports between modules with an automated check in CI (for example `import-linter`) once there are several modules.
- The whole application scales as one unit. If one module (likely `ingestion`) needs much more capacity than the rest, this decision should be revisited.

**How we will know it was a good decision**

- Adding the v1 modules (`banking`, `reconciliation`, `radian`) requires no changes to the internals of `ingestion` or `invoices`.
- A change in the invoice XML format is contained in the `invoices` module.
- The import-boundary check stays green in CI.
