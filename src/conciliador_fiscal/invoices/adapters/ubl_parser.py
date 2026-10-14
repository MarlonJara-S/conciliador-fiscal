"""Safe reading of DIAN electronic invoices (UBL 2.1 AttachedDocument).

The XML comes from third parties, so it is untrusted: no entity resolution,
no network, no DTDs. Real DIAN documents never carry a DOCTYPE, so any
document that has one is rejected.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from lxml import etree
from pydantic import ValidationError

from conciliador_fiscal.invoices.domain.models import (
    Invoice,
    InvoiceLine,
    MonetaryTotals,
    Party,
    TaxSubtotal,
)

NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
EMBEDDED_INVOICE_PATH = "cac:Attachment/cac:ExternalReference/cbc:Description"
PARTY_TAX_SCHEME = "cac:Party/cac:PartyTaxScheme"
TAX_SCHEME = "cac:TaxCategory/cac:TaxScheme"


class InvoiceParseError(Exception):
    """The document is not a readable invoice. Permanent error: goes to quarantine."""


def _parse_untrusted(data: bytes, what: str) -> etree._Element:
    """Parse one XML layer safely and reject it if it declares a DOCTYPE."""
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )
    try:
        root = etree.fromstring(data, parser)
    except etree.XMLSyntaxError as error:
        raise InvoiceParseError(f"{what} is not well-formed XML: {error}") from error
    # internalDTD is set for any <!DOCTYPE ...>, with or without an inline [ ] block.
    if root.getroottree().docinfo.internalDTD is not None:
        raise InvoiceParseError(f"{what} declares a DOCTYPE, which DIAN documents never have")
    return root


def load_embedded_invoice(data: bytes) -> etree._Element:
    """Parse an AttachedDocument and return the root element of the embedded Invoice.

    Raises InvoiceParseError if either XML layer is malformed or has a DOCTYPE,
    or if the envelope does not contain an invoice.
    """
    envelope = _parse_untrusted(data, "AttachedDocument")
    found = envelope.xpath(EMBEDDED_INVOICE_PATH, namespaces=NS)
    if not isinstance(found, list) or not found:
        raise InvoiceParseError("AttachedDocument does not contain an embedded invoice")
    description = found[0]
    if not isinstance(description, etree._Element) or not description.text:
        raise InvoiceParseError("Embedded invoice is empty")
    return _parse_untrusted(description.text.strip().encode(), "Embedded invoice")


def parse_invoice(data: bytes) -> Invoice:
    """Read an AttachedDocument and return the validated Invoice inside it.

    Raises InvoiceParseError for unsafe or malformed XML, missing data or data
    that breaks the domain rules (e.g. a wrong NIT check digit).
    """
    invoice = load_embedded_invoice(data)
    try:
        return Invoice(
            cufe=_text(invoice, "cbc:UUID"),
            number=_text(invoice, "cbc:ID"),
            issue_date=_date(invoice, "cbc:IssueDate"),
            currency=_text(invoice, "cbc:DocumentCurrencyCode"),
            supplier=_parse_party(_element(invoice, "cac:AccountingSupplierParty")),
            customer=_parse_party(_element(invoice, "cac:AccountingCustomerParty")),
            lines=[_parse_line(line) for line in invoice.findall("cac:InvoiceLine", NS)],
            taxes=[
                _parse_tax(subtotal)
                for subtotal in invoice.findall("cac:TaxTotal/cac:TaxSubtotal", NS)
            ],
            totals=_parse_totals(_element(invoice, "cac:LegalMonetaryTotal")),
        )
    except ValidationError as error:
        raise InvoiceParseError(f"Invoice breaks a domain rule: {error}") from error


def _parse_party(party: etree._Element) -> Party:
    """Build a Party from cac:AccountingSupplierParty or cac:AccountingCustomerParty."""

    name = _text(party, f"{PARTY_TAX_SCHEME}/cbc:RegistrationName")
    company_id = _element(party, f"{PARTY_TAX_SCHEME}/cbc:CompanyID")
    id_number = (company_id.text or "").strip()
    id_type = company_id.get("schemeName") or ""
    check_digit_str = company_id.get("schemeID")
    check_digit = int(check_digit_str) if check_digit_str else None

    return Party(
        name=name,
        id_number=id_number,
        id_type=id_type,
        check_digit=check_digit,
    )


def _parse_line(line: etree._Element) -> InvoiceLine:
    # A line may have several taxes (e.g. VAT + a municipal tax) or none (VAT-exempt books).
    tax_amount = sum(
        (_to_decimal(amount.text) for amount in line.findall("cac:TaxTotal/cbc:TaxAmount", NS)),
        start=Decimal("0"),
    )
    return InvoiceLine(
        description=_text(line, "cac:Item/cbc:Description"),
        quantity=_decimal(line, "cbc:InvoicedQuantity"),
        unit_price=_decimal(line, "cac:Price/cbc:PriceAmount"),
        line_total=_decimal(line, "cbc:LineExtensionAmount"),
        tax_amount=tax_amount,
    )


def _parse_tax(subtotal: etree._Element) -> TaxSubtotal:
    rate = subtotal.findtext("cac:TaxCategory/cbc:Percent", namespaces=NS)
    return TaxSubtotal(
        tax_id=_text(subtotal, f"{TAX_SCHEME}/cbc:ID"),
        tax_name=_text(subtotal, f"{TAX_SCHEME}/cbc:Name"),
        taxable_amount=_decimal(subtotal, "cbc:TaxableAmount"),
        tax_amount=_decimal(subtotal, "cbc:TaxAmount"),
        rate=_to_decimal(rate) if rate else None,
    )


def _parse_totals(totals: etree._Element) -> MonetaryTotals:
    return MonetaryTotals(
        line_extension_amount=_decimal(totals, "cbc:LineExtensionAmount"),
        tax_exclusive_amount=_decimal(totals, "cbc:TaxExclusiveAmount"),
        tax_inclusive_amount=_decimal(totals, "cbc:TaxInclusiveAmount"),
        payable_amount=_decimal(totals, "cbc:PayableAmount"),
    )


def _element(parent: etree._Element, path: str) -> etree._Element:
    found = parent.find(path, NS)
    if found is None:
        raise InvoiceParseError(f"Missing required element {path}")
    return found


def _text(parent: etree._Element, path: str) -> str:
    text = (_element(parent, path).text or "").strip()
    if not text:
        raise InvoiceParseError(f"Required element {path} is empty")
    return text


def _decimal(parent: etree._Element, path: str) -> Decimal:
    return _to_decimal(_text(parent, path))


def _to_decimal(text: str | None) -> Decimal:
    try:
        return Decimal((text or "").strip())
    except InvalidOperation as error:
        raise InvoiceParseError(f"Not a valid amount: {text!r}") from error


def _date(parent: etree._Element, path: str) -> date:
    text = _text(parent, path)
    try:
        return date.fromisoformat(text)
    except ValueError as error:
        raise InvoiceParseError(f"Not a valid date in {path}: {text!r}") from error
