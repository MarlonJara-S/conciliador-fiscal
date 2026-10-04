# ADR 0003: Data isolated per company (multi-tenant)

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

P1 stores invoices, suppliers and payments for several client companies (tenants) in one system ([ARCHITECTURE.md](../ARCHITECTURE.md)).

- An accountant works for **several companies** and must see all of them.
- A business owner must see **only their own company**.
- Suppliers often sell to several of the accountant's companies. What one company knows about a supplier (notes, contacts, how much it buys) is private to that company.
- The same invoice can belong to two tenants: if the accountant manages both the seller and the buyer, one CUFE is an issued invoice for one company and a received invoice for the other.
- A leak between companies is the worst possible failure for an accounting product: it exposes private financial data and legal documents.
- Constraints: one developer, one PostgreSQL database ([ADR 0001](0001-modular-monolith.md)), low operating cost.

## Decision

Use **one shared database and schema, with a `company_id` on every tenant-owned table**, and enforce isolation in two layers.

1. **Data model**
   - Every tenant-owned row carries `company_id`, including suppliers, invoices, lines, taxes and original documents.
   - Uniqueness is scoped to the company: suppliers are unique by `(company_id, nit)` and invoices by `(company_id, cufe)`. A supplier selling to three companies is stored three times; that duplication is accepted in exchange for isolation.
   - Users reach companies through memberships with a role (`accountant`, `owner`), so one accountant can belong to many companies.

2. **Enforcement**
   - **From v0:** every query in the application filters by the current company, and tests check it.
   - **From v1 (week 22):** PostgreSQL **Row-Level Security** as a second, independent barrier. The application sets the current company per transaction (`SET LOCAL` through `set_config`, which also works with PgBouncer in transaction mode), and policies only return rows of that company. The application connects with a role that does not own the tables, and the tables use `FORCE ROW LEVEL SECURITY`, so a forgotten filter in the code still cannot leak data.

## Alternatives considered

**Schema per company.** Rejected. Every migration must run once per schema, the number of schemas grows with clients, and cross-company views for the accountant become unions over many schemas. Isolation is strong, but the operational cost is too high for one developer.

**Database per company.** Rejected. It gives the strongest isolation, but multiplies connections, backups, migrations and cost per client. It makes sense for large customers with contractual requirements, not for small businesses.

**Shared tables filtered only in application code.** Rejected as the final state. A single forgotten `WHERE company_id = ...` leaks data, and nothing catches it. It is acceptable only during v0, before RLS is added, and only with isolation tests.

**One shared supplier record for all companies.** Rejected. Any change by one company (notes, contact data) would appear in the others, and the record could reveal which other companies buy from that supplier.

## Consequences

**Positive**

- One schema and one migration path for all companies; cheap to operate.
- Two independent barriers once RLS is in place: a bug in the application is not enough to leak data.
- Cross-company views for the accountant are ordinary queries over the companies they belong to.

**Negative and risks**

- Every table, query and index must include `company_id`. Composite indexes should usually start with it.
- Between v0 and v1 isolation depends only on application code. Mitigation: isolation tests from the first version that stores data.
- RLS adds complexity: setting the company per transaction, connection pooling, and making sure the application role never bypasses policies.
- Supplier data is duplicated across companies.

**How we will know it was a good decision**

- An automated test proves that a user of company A cannot read company B's invoices, both through the API and with direct SQL using the application role.
- No leak is found in the security review (`security-reviewer`) or in the red-teaming of the AI assistant in v2.
- Adding a new company requires no migration or infrastructure change.
