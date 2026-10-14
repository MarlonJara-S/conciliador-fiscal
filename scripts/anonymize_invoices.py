"""Create anonymized copies of real invoices to use as test fixtures.

Reads the private ZIP files in data/private/facturas, replaces the customer's personal
data and every document identifier (CUFE/CUDE), and writes plain XML files to
tests/fixtures/invoices.

Kept as they are: supplier data (public company records), products and amounts (not
personal, and exactly what the tests need). The originals are never modified. The
digital signature of each copy becomes invalid, which does not matter for parsing tests.

Usage, from the project root:
    python scripts/anonymize_invoices.py
"""

import hashlib
import re
import sys
import zipfile
from pathlib import Path

SOURCE_DIR = Path("data/private/facturas")
TARGET_DIR = Path("tests/fixtures/invoices")
# Optional, private: personal values the script cannot detect on its own
# (another ID, a nickname, an old email...), one per line. Never committed.
EXTRA_VALUES_FILE = Path("data/private/extra_personal_values.txt")

FAKE_NAME = "CLIENTE DE PRUEBA"
FAKE_EMAIL = "cliente@example.com"
FAKE_ADDRESS = "CALLE FALSA 123"
FAKE_DIGITS = "1234567890"
MIN_VALUE_LENGTH = 3  # shorter values ("CO", "-") are codes, not personal data
MIN_NAME_WORD_LENGTH = 4  # name words shorter than this ("DE", "LA") are not identifying
PLACEHOLDERS = {"no aplica", "n/a", "ninguno", "consumidor final", "sin direccion"}

CUSTOMER_BLOCK = re.compile(
    r"<(?:\w+:)?AccountingCustomerParty\b.*?</(?:\w+:)?AccountingCustomerParty>", re.S
)
# A CUFE or CUDE: a SHA-384 hash written as 96 hexadecimal characters.
DOCUMENT_ID = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{96}(?![0-9a-fA-F])")
# Some issuers print the raw text used to compute the CUFE: all invoice fields glued
# together, including the customer's ID. No test needs it, so its content is removed.
CUFE_INPUT_NOTE = re.compile(r"(String:)[^<]*")
MIN_STRICT_NUMBER_LENGTH = 8  # long numbers (IDs) are searched even inside other digits

# Each pattern captures one personal value inside the customer block, with its kind.
PERSONAL_FIELDS = [
    (r"<(?:\w+:)?(?:RegistrationName|FirstName|MiddleName|FamilyName)\b[^>]*>([^<]+)<", "name"),
    (r"<(?:\w+:)?PartyName>\s*<(?:\w+:)?Name\b[^>]*>([^<]+)<", "name"),
    (r"<(?:\w+:)?(?:CompanyID|SupplierAssignedAccountID)\b[^>]*>([^<]+)<", "number"),
    (r"<(?:\w+:)?PartyIdentification>\s*<(?:\w+:)?ID\b[^>]*>([^<]+)<", "number"),
    (r"<(?:\w+:)?(?:Telephone|Telefax)\b[^>]*>([^<]+)<", "number"),
    (r"<(?:\w+:)?ElectronicMail\b[^>]*>([^<]+)<", "email"),
    (r"<(?:\w+:)?AddressLine>\s*<(?:\w+:)?Line\b[^>]*>([^<]+)<", "address"),
]


def fake_number(value: str) -> str:
    """Replace each digit, keeping the length and any spaces or symbols."""
    digits = iter(FAKE_DIGITS * (len(value) // len(FAKE_DIGITS) + 1))
    return "".join(next(digits) if char.isdigit() else char for char in value)


def fake_value(value: str, kind: str) -> str:
    if kind == "number":
        return fake_number(value)
    if kind == "email":
        return FAKE_EMAIL
    if kind == "address":
        return FAKE_ADDRESS
    return FAKE_NAME


def find_personal_values(xml: str) -> dict[str, str]:
    """Map each personal value of the customer to its fake replacement."""
    # Some issuers add extra, empty customer blocks in their own extensions,
    # so every block is checked, not just the first one.
    blocks = [match.group(0) for match in CUSTOMER_BLOCK.finditer(xml)]
    if not blocks:
        raise ValueError("No AccountingCustomerParty found")
    replacements: dict[str, str] = {}
    for block in blocks:
        for pattern, kind in PERSONAL_FIELDS:
            for match in re.finditer(pattern, block):
                value = match.group(1).strip()
                if len(value) < MIN_VALUE_LENGTH or value.lower() in PLACEHOLDERS:
                    continue
                replacements[value] = fake_value(value, kind)
                if kind == "name":
                    # Names also appear in other orders ("SURNAME NAME"): replace each word.
                    for word in value.split():
                        if len(word) >= MIN_NAME_WORD_LENGTH:
                            replacements.setdefault(word, FAKE_NAME)
    return replacements


def read_extra_values() -> dict[str, str]:
    """Personal values listed by hand in the private file, with their fakes."""
    if not EXTRA_VALUES_FILE.exists():
        return {}
    extra: dict[str, str] = {}
    for raw_line in EXTRA_VALUES_FILE.read_text(encoding="utf-8").splitlines():
        value = raw_line.strip()
        if not value or value.startswith("#"):
            continue
        kind = "number" if value.isdigit() else "email" if "@" in value else "name"
        extra[value] = fake_value(value, kind)
    return extra


def replace_value(xml: str, value: str, fake: str) -> str:
    if value.isdigit():
        # Do not touch the same digits when they are part of a longer number.
        return re.sub(rf"(?<!\d){re.escape(value)}(?!\d)", fake, xml)
    return xml.replace(value, fake)


def fake_document_id(match: re.Match[str]) -> str:
    """Same input, same fake ID: references between documents stay consistent."""
    return hashlib.sha384(b"fixture:" + match.group(0).encode()).hexdigest()


def anonymize(xml: str, personal: dict[str, str]) -> str:
    # Longest first, so a full name is replaced before any of its words.
    for value in sorted(personal, key=len, reverse=True):
        xml = replace_value(xml, value, personal[value])
    xml = CUFE_INPUT_NOTE.sub(r"\1 removed", xml)
    return DOCUMENT_ID.sub(fake_document_id, xml)


def find_leaks(xml: str, personal: dict[str, str]) -> int:
    """Count personal values still present in the output.

    Stricter than the replacement: long numbers are searched anywhere, even glued to
    other digits. A false alarm is better than a leak.
    """

    def pattern_for(value: str) -> str:
        if value.isdigit() and len(value) < MIN_STRICT_NUMBER_LENGTH:
            return rf"(?<!\d){re.escape(value)}(?!\d)"
        return re.escape(value)

    return sum(1 for value in personal if re.search(pattern_for(value), xml))


def read_invoice_xml(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if len(xml_names) != 1:
            raise ValueError(f"{zip_path.name}: expected 1 XML file, found {len(xml_names)}")
        return archive.read(xml_names[0]).decode("utf-8")


def main() -> int:
    zip_paths = sorted(SOURCE_DIR.glob("*.zip"))
    if not zip_paths:
        print(f"No ZIP files found in {SOURCE_DIR}")
        return 1

    originals = [read_invoice_xml(zip_path) for zip_path in zip_paths]

    # All invoices belong to the same customer: collect their data from every invoice,
    # so a value hidden in an unusual structure in one file is still caught in the others.
    personal: dict[str, str] = {}
    for xml in originals:
        personal.update(find_personal_values(xml))
    extra = read_extra_values()
    personal.update(extra)
    print(f"{len(extra)} extra values read from {EXTRA_VALUES_FILE}")

    anonymized = [anonymize(xml, personal) for xml in originals]
    leaks = sum(find_leaks(xml, personal) for xml in anonymized)
    if leaks:
        print(f"Aborted: {leaks} personal values are still in the output. Nothing was written.")
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    for number, xml in enumerate(anonymized, start=1):
        target = TARGET_DIR / f"invoice_{number:02d}.xml"
        target.write_text(xml, encoding="utf-8")
        print(f"{target} written")
    print(f"{len(personal)} personal values replaced in {len(anonymized)} invoices; no leaks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
