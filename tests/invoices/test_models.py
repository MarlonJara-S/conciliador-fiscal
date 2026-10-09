from decimal import Decimal

import pytest
from pydantic import ValidationError

from conciliador_fiscal.invoices.domain.models import InvoiceLine, Party


def test_valid_line_is_created() -> None:
    line = InvoiceLine(
        description="Harina de trigo 50kg",
        quantity=Decimal("10"),
        unit_price=Decimal("100000"),
        line_total=Decimal("100000"),
        tax_amount=Decimal("190000"),
    )

    assert line.quantity == Decimal("10")


def test_gift_line_with_zero_price_is_accepted() -> None:
    line = InvoiceLine(
        description="Pañitos humedos",
        quantity=Decimal("10"),
        unit_price=Decimal("0"),
        line_total=Decimal("0"),
        tax_amount=Decimal("0"),
    )
    assert line.line_total == Decimal("0")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("description", ""),
        ("quantity", Decimal("0")),
        ("quantity", Decimal("-10")),
        ("unit_price", Decimal("-10")),
        ("line_total", Decimal("-10")),
        ("tax_amount", Decimal("-10")),
    ],
)
def test_invalid_values_are_rejected(field: str, value: object) -> None:
    data = {
        "description": "Harina de trigo 50 kg",
        "quantity": Decimal("10"),
        "unit_price": Decimal("100000"),
        "line_total": Decimal("1000000"),
        "tax_amount": Decimal("190000"),
    }
    data[field] = value  # reemplaza un solo campo por el valor malo

    with pytest.raises(ValidationError):
        InvoiceLine(**data)


def test_party_with_valid_nit_is_created() -> None:
    party = Party(
        name="DIAN",
        id_type="31",
        id_number="800197268",
        check_digit=4,
    )

    assert party.check_digit == 4


def test_party_with_wrong_check_digit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Party(
            name="DIAN",
            id_type="31",
            id_number="800197268",
            check_digit=5,  # the correct check digit is 4
        )


def test_party_with_nit_without_check_digit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Party(
            name="DIAN",
            id_type="31",
            id_number="800197268",
            check_digit=None,  # a NIT always has a check digit
        )


def test_party_with_cedula_without_check_digit_is_created() -> None:
    party = Party(
        name="Laura Gómez",
        id_type="13",
        id_number="1234567890",
        check_digit=None,  # a cédula has no check digit
    )

    assert party.check_digit is None
