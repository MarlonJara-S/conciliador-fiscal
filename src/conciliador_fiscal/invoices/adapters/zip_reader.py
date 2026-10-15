"""Extract the XML document from the ZIP attached to an invoice email.

The ZIP comes from third parties, so it is untrusted: it is never extracted
to disk (no zip slip), and entries are read with a size limit, because the
sizes written in the ZIP index can lie (zip bomb).
"""

import io
import zipfile

from conciliador_fiscal.invoices.adapters.ubl_parser import InvoiceParseError

MAX_ENTRIES = 10  # real attachments carry 2 files: the XML and its PDF
MAX_XML_BYTES = 5 * 1024 * 1024  # real XMLs weigh ~50 KB
XML_EXTENSION = ".xml"


def extract_xml(data: bytes) -> bytes:
    """Return the only XML document inside the ZIP attachment.

    Raises InvoiceParseError if the data is not a ZIP, has too many entries,
    does not contain exactly one XML, or the XML is too big once decompressed.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise InvoiceParseError(f"Attachment is not a valid ZIP: {error}") from error

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            raise InvoiceParseError(f"ZIP has {len(entries)} entries (max {MAX_ENTRIES})")

        xml_entries = [e for e in entries if e.filename.lower().endswith(XML_EXTENSION)]
        if len(xml_entries) != 1:
            raise InvoiceParseError(f"ZIP must contain one XML document, found {len(xml_entries)}")
        entry = xml_entries[0]

        # First defense: the size the index declares (cheap, but the index can lie).
        if entry.file_size > MAX_XML_BYTES:
            raise InvoiceParseError(f"{entry.filename} declares {entry.file_size} bytes")

        # Second defense: never read more than the limit, whatever the index says.
        with archive.open(entry) as stream:
            content = stream.read(MAX_XML_BYTES + 1)
        if len(content) > MAX_XML_BYTES:
            raise InvoiceParseError(f"{entry.filename} is bigger than {MAX_XML_BYTES} bytes")
        return content
