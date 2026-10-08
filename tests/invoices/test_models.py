from decimal import Decimal

import pytest
from pydantic import ValidationError

from conciliador_fiscal.invoices.domain.models import InvoiceLine


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
