import hashlib
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from conciliador_fiscal.invoices.domain.models import (
    Invoice,
    InvoiceLine,
    MonetaryTotals,
    Party,
    TaxSubtotal,
)

# A CUFE is a SHA-384 hash written in hexadecimal: always 96 characters.
VALID_CUFE = hashlib.sha384(b"example invoice").hexdigest()


def make_invoice(**overrides: Any) -> Invoice:
    """Build a valid invoice; each test overrides only the field it is about."""
    data: dict[str, Any] = {
        "cufe": VALID_CUFE,
        "number": "FE-1042",
        "issue_date": date(2026, 10, 5),
        "currency": "COP",
        "supplier": Party(
            name="Harinas del Valle S.A.S.",
            id_type="31",
            id_number="890903938",
            check_digit=8,
        ),
        "customer": Party(
            name="Laura Gómez",
            id_type="13",
            id_number="1234567890",
        ),
        "lines": [
            InvoiceLine(
                description="Harina de trigo 50 kg",
                quantity=Decimal("10"),
                unit_price=Decimal("100000"),
                line_total=Decimal("1000000"),
                tax_amount=Decimal("190000"),
            )
        ],
        "taxes": [
            TaxSubtotal(
                tax_id="01",
                tax_name="IVA",
                taxable_amount=Decimal("1000000"),
                rate=Decimal("19.00"),
                tax_amount=Decimal("190000"),
            )
        ],
        "totals": MonetaryTotals(
            line_extension_amount=Decimal("1000000"),
            tax_exclusive_amount=Decimal("1000000"),
            tax_inclusive_amount=Decimal("1190000"),
            payable_amount=Decimal("1190000"),
        ),
    }
    data.update(overrides)
    return Invoice(**data)


def test_valid_invoice_is_created() -> None:
    invoice = make_invoice()

    assert invoice.totals.payable_amount == Decimal("1190000")
    assert invoice.supplier.check_digit == 8


@pytest.mark.parametrize(
    "cufe",
    [
        VALID_CUFE[:-1],  # 95 characters: one short
        VALID_CUFE[:-1] + "g",  # "g" is not a hexadecimal digit
        "",
    ],
)
def test_malformed_cufe_is_rejected(cufe: str) -> None:
    with pytest.raises(ValidationError):
        make_invoice(cufe=cufe)


def test_invoice_without_lines_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_invoice(lines=[])


def test_currency_must_be_an_iso_code() -> None:
    with pytest.raises(ValidationError):
        make_invoice(currency="pesos")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("taxable_amount", Decimal("-1")),
        ("rate", Decimal("-1")),
        ("rate", Decimal("101")),
        ("tax_amount", Decimal("-1")),
        ("tax_id", ""),
    ],
)
def test_invalid_tax_subtotal_is_rejected(field: str, value: object) -> None:
    data: dict[str, Any] = {
        "tax_id": "01",
        "tax_name": "IVA",
        "taxable_amount": Decimal("1000000"),
        "rate": Decimal("19.00"),
        "tax_amount": Decimal("190000"),
    }
    data[field] = value

    with pytest.raises(ValidationError):
        TaxSubtotal(**data)


def test_negative_payable_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MonetaryTotals(
            line_extension_amount=Decimal("1000000"),
            tax_exclusive_amount=Decimal("1000000"),
            tax_inclusive_amount=Decimal("1190000"),
            payable_amount=Decimal("-1"),
        )


def test_models_cannot_be_changed_after_creation() -> None:
    party = Party(name="DIAN", id_type="31", id_number="800197268", check_digit=4)

    with pytest.raises(ValidationError):
        party.check_digit = 9  # would silently break the check digit rule
