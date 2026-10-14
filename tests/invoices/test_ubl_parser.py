from pathlib import Path

import pytest

from conciliador_fiscal.invoices.adapters.ubl_parser import (
    NS,
    InvoiceParseError,
    load_embedded_invoice,
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
