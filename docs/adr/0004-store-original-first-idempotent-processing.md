# ADR 0004: Store the original document first and process idempotently

- **Status:** Accepted
- **Date:** 2026-10-03

## Context

Invoices arrive from outside the system, by email and later by manual upload ([ARCHITECTURE.md](../ARCHITECTURE.md)). That input is unreliable in several ways:

- The same email can arrive twice, and the same invoice can arrive in different emails.
- XML from hundreds of different issuers can be malformed, unexpected or malicious.
- Workers can crash, be restarted or be killed in the middle of processing a document.
- Our own parser will have bugs, and it will change as we learn the real invoice formats.
- Colombian rules require keeping the received XML for years.

The project rule ([CLAUDE.md](../../CLAUDE.md)) already states that every write caused by an external event must be idempotent and have a concurrency test. This ADR defines how ingestion meets it.

## Decision

**1. Store the original first, exactly as received, before any parsing.**

- Raw bytes (ZIP, XML, PDF) are stored immutably and identified by their SHA-256 hash. A metadata row records the company, source (email `Message-ID` or upload), hash and status.
- Development: a local directory ignored by Git. Production: object storage (S3) with versioning and lifecycle rules for long retention.
- Every later step reads from the stored original, never from the mailbox again.

**2. Make every step idempotent, with deduplication at three levels.**

| Level | Key | Prevents |
|---|---|---|
| Message | Mailbox + `Message-ID` | Processing the same email twice |
| Document | Company + SHA-256 of the file | Storing the same attachment twice |
| Invoice | Company + CUFE (unique constraint, `INSERT ... ON CONFLICT`) | Storing the same invoice from different emails |

**3. Process through a queue with at-least-once delivery.**

- A task is acknowledged only after it finishes (late acknowledgement). If a worker dies, the task is delivered again and processing **restarts from the beginning** for that document. Restarting is safe because every step is idempotent.
- **Temporary errors** (database or network unavailable) are retried with exponential backoff and jitter, up to a limit.
- **Permanent errors** (malformed XML, attack attempts, failed validation) send the document to **quarantine** with the reason. It is never deleted, it does not block the rest of the batch, and it can be reprocessed after a fix.

## Alternatives considered

**Parse in memory and keep only the extracted data.** Rejected. It breaks the legal retention requirement, and a parser bug would permanently lose information with no way to reprocess.

**Rely on the queue for "exactly-once" processing.** Rejected. Queues and email deliver messages at least once in practice; exactly-once across a mailbox, a queue and a database would need distributed transactions. Idempotent steps give the same result with much less complexity.

**Checkpoint after every step and resume where it stopped.** Rejected for invoice ingestion. Processing one document takes seconds, so restarting it is cheaper than persisting intermediate state. Durable execution is reserved for long workflows that span days, such as DIAN RADIAN deadlines.

**Store the original bytes inside PostgreSQL.** Rejected as the long-term solution. Years of XML and PDF files would inflate the database, its backups and its restore time. Object storage is cheaper and built for this.

## Consequences

**Positive**

- No document is ever lost: anything that reached the system can be reprocessed from its original.
- Duplicates are prevented at three independent levels.
- A bad document affects only itself; the rest of the batch continues.
- Parser changes can be applied to old documents by reprocessing them.

**Negative and risks**

- Extra storage for originals, which grows for years. Mitigation: lifecycle rules that move old files to cheaper storage classes.
- Every new step must be designed to be safely repeatable; a non-idempotent side effect (for example, sending a notification) needs its own deduplication.
- Quarantined documents need someone to review them. Mitigation: an "Invoices with problems" view for the accountant, with the reason for each one.

**How we will know it was a good decision**

- 10,000 invoices are ingested with no duplicates and no losses, even when workers are killed in the middle of processing (P1 definition of done).
- A concurrency test that loads the same invoice 100 times in parallel stores exactly one row.
- Reprocessing all stored originals reproduces the same invoices in the database.
