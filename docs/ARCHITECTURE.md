# Architecture

High-level design of P1, the tax reconciliation system for small Colombian businesses. Detailed database schemas are defined later (week 12), once the real invoice XML is well understood. Decisions are recorded in [`docs/adr/`](adr/).

## 1. Problem

Small businesses in Colombia receive electronic invoices (UBL 2.1 XML, validated by the tax authority, DIAN) from their suppliers by email. Today an accountant handles them by hand:

1. Opens the email of each client company and downloads the ZIP attachments.
2. Types the invoice data (supplier, tax ID, date, subtotal, VAT, total) into a spreadsheet or accounting software.
3. Catches duplicates when a supplier sends the same invoice twice.
4. Once a month, matches bank statement payments against invoices. Amounts rarely match exactly: customers deduct withholding taxes, pay partially, or pay several invoices in one transfer.
5. Tracks legal deadlines for DIAN acceptance events (RADIAN) in a notebook or from memory.
6. Answers the business owner's questions ("How much did we buy from this supplier this year?") by searching spreadsheets.

### Users and external systems

| Actor | Type | Needs |
|---|---|---|
| Accountant | Main user | Works daily for **several companies**: reviews invoices, reconciles payments, meets deadlines |
| Business owner | Read-mostly user | Sees **only their own company**: purchases, unpaid invoices |
| Suppliers | External | Send invoices by email; never use the system |
| Bank | External | Source of the statements with payments |
| DIAN | External | Validates invoices and receives RADIAN events, with legal deadlines |

### Priorities

Pains are ranked by frequency × impact and by dependency (nothing can be reconciled before invoices are in the system):

| Version | Solves | Why in this order |
|---|---|---|
| v0 | Automatic invoice ingestion without duplicates (pains 2 and 3) | Everything else needs the invoices in the system |
| v1 | Payment reconciliation and DIAN deadlines (pains 4 and 5) | Builds on stored invoices; adds bank statements and timers |
| v2 | Natural-language questions with AI (pain 6) | The assistant queries data that already exists and is clean |

## 2. Main flow: the journey of an invoice

```
Email ─▶ which company? ─▶ store original ─▶ already processed? ─▶ queue
                                                                    │
        ┌───────────────────────────────────────────────────────────┘
        ▼
  unzip ─▶ extract invoice ─▶ validate ─▶ store (unique per CUFE) ─▶ accountant's inbox
                  │               │
                  └──── error ────┴─▶ permanent: quarantine + reason
                                       temporary: retry later
```

| Step | Why it exists |
|---|---|
| Identify the company | The accountant manages several companies; data must never leak between them |
| Store the original first | The law requires keeping the XML for years, and a parser bug must never lose a document: it can be reprocessed |
| Skip processed emails | The same email can arrive twice |
| Extract the invoice | The real invoice is embedded inside an `AttachedDocument` (XML inside XML) |
| Validate | Bad data must not reach reconciliation |
| Store uniquely by CUFE | The same invoice can arrive in different emails |

### Failure handling

- **Permanent errors** (malformed XML, attack attempts): the document goes to quarantine with the reason. It is never deleted, and the accountant sees it under "Invoices with problems". Processing continues with the next document.
- **Temporary errors** (the database did not respond): retry with backoff before giving up.
- **Crash mid-process:** the task is removed from the queue only when it finishes, so another worker picks it up and starts that invoice again from the beginning. This is safe because every step is idempotent: the original is already stored and the invoice is unique by CUFE.

## 3. Modules

P1 is a **modular monolith** ([ADR 0001](adr/0001-modular-monolith.md)): one application and one database, divided into modules with a single responsibility each.

| Module | Version | Responsibility |
|---|---|---|
| `ingestion` | v0 | Receive emails, identify the company, store the original, skip processed messages |
| `invoices` | v0 | Unzip, parse XML safely, extract and validate the invoice |
| `storage` | v0 | Persist data idempotently |
| `api` | v0 | Serve data to the accountant and the business owner |
| `banking` | v1 | Read and normalize bank statements |
| `reconciliation` | v1 | Match payments with invoices, including withholding taxes |
| `radian` | v1 | Track DIAN legal deadlines with durable workflows |
| `assistant` | v2 | Answer questions in natural language (read-only access) |

Rules:

- **One owner per piece of data.** Only `invoices` parses XML; other modules ask for invoices that are already parsed and validated.
- **A change lives in one module.** A new delivery channel (manual upload) only changes `ingestion`; a new XML format only changes `invoices`.

## 4. Domain entities (v0)

| Entity | Meaning | Uniqueness |
|---|---|---|
| Company | Each small business the accountant serves (the tenant) | Tax ID (NIT) |
| Supplier | A business that sells to a company and sends it invoices | Company + NIT |
| Invoice | What was sold and how much is owed | Company + CUFE |
| Invoice line | Each product or service in an invoice | Within its invoice |
| Tax | VAT (and other taxes) per line; one invoice can have several rates | Within its line |
| Original document | The ZIP and XML exactly as received, kept for legal retention | Content hash |

```
Company ──has many──▶ Invoices ◀──sends many── Supplier
                        │
                        ├──has many──▶ Lines ──have──▶ Taxes
                        └──comes from─▶ Original document
```

**Everything belongs to a company.** A supplier that sells to three companies is stored once per company: duplicating its name and NIT is the price of keeping each company's data isolated (multi-tenant).

## 5. Glossary

| Term | Meaning |
|---|---|
| DIAN | Colombia's tax authority |
| UBL 2.1 | XML standard used for Colombian electronic invoices |
| CUFE | Unique code of each electronic invoice |
| NIT | Tax identification number of a company |
| AttachedDocument | XML envelope that carries the invoice inside it |
| Reconciliation | Matching bank payments with invoices to know which are paid |
| Withholding tax | Part of a payment the customer keeps and pays to DIAN on the supplier's behalf; the reason payments are lower than invoice totals |
| RADIAN | DIAN's registry of invoice events (receipt, acceptance) with legal deadlines |
| Tenant | Each client company whose data is isolated from the others |
