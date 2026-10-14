# Invoice fixtures

Real Colombian electronic invoices (UBL 2.1 `AttachedDocument` with the embedded `Invoice` and the DIAN `ApplicationResponse`), anonymized for use in tests.

- **Replaced:** the customer's personal data (names, ID number, email, phone, address) and every document identifier (CUFE/CUDE), which is mapped to a fake SHA-384 hash.
- **Kept:** supplier data (public company records), products, amounts and the document structure, including issuer-specific quirks.
- **Digital signatures are invalid** in these copies. Signature verification must use the private originals.

Generated with `python scripts/anonymize_invoices.py` from the private originals in `data/private/facturas/` (never committed). The script aborts without writing anything if any personal value would remain in the output.
