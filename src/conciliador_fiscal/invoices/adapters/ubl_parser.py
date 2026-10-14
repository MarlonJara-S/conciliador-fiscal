"""Safe reading of DIAN electronic invoices (UBL 2.1 AttachedDocument).

The XML comes from third parties, so it is untrusted: no entity resolution,
no network, no DTDs. Real DIAN documents never carry a DOCTYPE, so any
document that has one is rejected.
"""

from lxml import etree

NS = {
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
}
EMBEDDED_INVOICE_PATH = "cac:Attachment/cac:ExternalReference/cbc:Description"


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
