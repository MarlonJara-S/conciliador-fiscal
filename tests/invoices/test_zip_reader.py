import io
import zipfile
from pathlib import Path

import pytest

from conciliador_fiscal.invoices.adapters.ubl_parser import InvoiceParseError, parse_invoice
from conciliador_fiscal.invoices.adapters.zip_reader import (
    MAX_ENTRIES,
    MAX_XML_BYTES,
    extract_xml,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "invoices"
FAKE_PDF = b"%PDF-1.4 fake invoice representation"


def make_zip(entries: dict[str, bytes]) -> bytes:
    """Build a ZIP in memory, like the attachment of an invoice email."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_xml_is_extracted_and_parsed() -> None:
    xml = (FIXTURES / "invoice_01.xml").read_bytes()
    attachment = make_zip({"ad0900422614.xml": xml, "ad0900422614.pdf": FAKE_PDF})

    extracted = extract_xml(attachment)

    assert extracted == xml
    assert parse_invoice(extracted).number == "DC16639102"


def test_xml_is_found_whatever_the_order_and_name_case() -> None:
    xml = (FIXTURES / "invoice_02.xml").read_bytes()
    attachment = make_zip({"z123.pdf": FAKE_PDF, "FV-0042.XML": xml})

    assert extract_xml(attachment) == xml


def test_data_that_is_not_a_zip_is_rejected() -> None:
    with pytest.raises(InvoiceParseError):
        extract_xml(b"this is not a zip file")


def test_zip_without_xml_is_rejected() -> None:
    with pytest.raises(InvoiceParseError):
        extract_xml(make_zip({"invoice.pdf": FAKE_PDF}))


def test_zip_with_two_xml_documents_is_rejected() -> None:
    with pytest.raises(InvoiceParseError):
        extract_xml(make_zip({"a.xml": b"<a/>", "b.xml": b"<b/>"}))


def test_zip_with_too_many_entries_is_rejected() -> None:
    entries = {f"file_{n}.txt": b"x" for n in range(MAX_ENTRIES)}
    entries["invoice.xml"] = b"<Invoice/>"

    with pytest.raises(InvoiceParseError):
        extract_xml(make_zip(entries))


def test_zip_bomb_is_rejected() -> None:
    # A few KB compressed, more than the limit once decompressed.
    bomb = b"<" + b" " * MAX_XML_BYTES
    attachment = make_zip({"invoice.xml": bomb})
    assert len(attachment) < 100_000

    with pytest.raises(InvoiceParseError):
        extract_xml(attachment)
