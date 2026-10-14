from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from conciliador_fiscal.invoices.adapters.ubl_parser import (
    NS,
    InvoiceParseError,
    load_embedded_invoice,
    parse_invoice,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "invoices"
INVOICE_TAG = "{urn:oasis:names:specification:ubl:schema:xsd:Invoice-2}Invoice"

XXE_DOCTYPE = '<!DOCTYPE Invoice [<!ENTITY secret SYSTEM "file:///etc/passwd">]>'
MINIMAL_INVOICE = (
    '<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"'
    f' xmlns:cbc="{NS["cbc"]}"><cbc:ID>FE-1</cbc:ID></Invoice>'
)


def make_envelope(inner: str, envelope_doctype: str = "") -> bytes:
    """Build a minimal AttachedDocument whose embedded invoice is `inner`."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"{envelope_doctype}"
        '<AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2"'
        f' xmlns:cac="{NS["cac"]}" xmlns:cbc="{NS["cbc"]}">'
        "<cac:Attachment><cac:ExternalReference>"
        f"<cbc:Description><![CDATA[{inner}]]></cbc:Description>"
        "</cac:ExternalReference></cac:Attachment>"
        "</AttachedDocument>"
    ).encode()


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.xml")), ids=lambda p: p.name)
def test_real_invoices_are_loaded(path: Path) -> None:
    invoice = load_embedded_invoice(path.read_bytes())

    assert invoice.tag == INVOICE_TAG
    assert invoice.xpath("cbc:UUID/@schemeName", namespaces=NS) == ["CUFE-SHA384"]


def test_minimal_envelope_is_loaded() -> None:
    invoice = load_embedded_invoice(make_envelope(MINIMAL_INVOICE))

    assert invoice.findtext("cbc:ID", namespaces=NS) == "FE-1"


def test_envelope_with_doctype_is_rejected() -> None:
    with pytest.raises(InvoiceParseError):
        load_embedded_invoice(make_envelope(MINIMAL_INVOICE, envelope_doctype=XXE_DOCTYPE))


def test_embedded_invoice_with_doctype_is_rejected() -> None:
    # The envelope is clean; the attack hides in the second layer.
    with pytest.raises(InvoiceParseError):
        load_embedded_invoice(make_envelope(XXE_DOCTYPE + MINIMAL_INVOICE))


@pytest.mark.parametrize(
    "data",
    [b"", b"<AttachedDocument>", b"not xml at all"],
    ids=["empty", "unclosed", "text"],
)
def test_malformed_envelope_is_rejected(data: bytes) -> None:
    with pytest.raises(InvoiceParseError):
        load_embedded_invoice(data)


def test_malformed_embedded_invoice_is_rejected() -> None:
    with pytest.raises(InvoiceParseError):
        load_embedded_invoice(make_envelope("<Invoice>"))


def test_envelope_without_invoice_is_rejected() -> None:
    data = (
        f'<AttachedDocument xmlns:cbc="{NS["cbc"]}">'
        "<cbc:Note>no attachment here</cbc:Note>"
        "</AttachedDocument>"
    ).encode()

    with pytest.raises(InvoiceParseError):
        load_embedded_invoice(data)


# --- From the Invoice element to the domain model ---


def read_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.xml")), ids=lambda p: p.name)
def test_real_invoices_are_parsed(path: Path) -> None:
    invoice = parse_invoice(path.read_bytes())

    assert invoice.currency == "COP"
    assert invoice.supplier.id_type == "31"  # every supplier is a company with a NIT


def test_header_supplier_and_customer_are_read() -> None:
    invoice = parse_invoice(read_fixture("invoice_01.xml"))

    assert invoice.number == "DC16639102"
    assert invoice.issue_date == date(2026, 2, 14)
    assert invoice.supplier.name == "EXPERIAN COLOMBIA S.A."
    assert invoice.supplier.id_number == "900422614"
    assert invoice.supplier.check_digit == 8
    assert invoice.customer.id_type == "13"
    assert invoice.customer.check_digit is None  # empty schemeID


def test_amounts_are_read_as_decimals() -> None:
    invoice = parse_invoice(read_fixture("invoice_01.xml"))

    assert invoice.lines[0].line_total == Decimal("20084.00")
    assert invoice.taxes[0].rate == Decimal("19.00")
    assert invoice.taxes[0].tax_amount == Decimal("3815.96")
    assert invoice.totals.payable_amount == Decimal("23899.96")


def test_line_with_two_taxes_adds_them() -> None:
    invoice = parse_invoice(read_fixture("invoice_02.xml"))

    assert invoice.lines[0].tax_amount == Decimal("3995.00") + Decimal("1600.00")


def test_fixed_per_unit_tax_has_no_rate() -> None:
    invoice = parse_invoice(read_fixture("invoice_02.xml"))

    phone_tax = next(tax for tax in invoice.taxes if tax.tax_id == "ZZ")
    assert phone_tax.rate is None
    assert phone_tax.tax_amount == Decimal("1600.00")


def test_vat_exempt_invoice_has_no_taxes() -> None:
    invoice = parse_invoice(read_fixture("invoice_10.xml"))

    assert invoice.taxes == []
    assert invoice.lines[0].tax_amount == Decimal("0")


def test_invoice_with_missing_data_is_rejected() -> None:
    with pytest.raises(InvoiceParseError):
        parse_invoice(make_envelope(MINIMAL_INVOICE))


def test_invoice_breaking_a_domain_rule_is_rejected() -> None:
    wrong_check_digit = read_fixture("invoice_01.xml").replace(
        b'schemeID="8" schemeName="31">900422614', b'schemeID="9" schemeName="31">900422614'
    )

    with pytest.raises(InvoiceParseError):
        parse_invoice(wrong_check_digit)
