from decimal import Decimal

from conciliador_fiscal.taxes import calculate_vat


def test_vat_on_round_amount() -> None:
    assert calculate_vat(Decimal("1000"), Decimal("0.19")) == Decimal("190.00")


def test_vat_rounds_to_two_decimals() -> None:
    assert calculate_vat(Decimal("33.33"), Decimal("0.19")) == Decimal("6.33")


def test_vat_with_zero_rate() -> None:
    assert calculate_vat(Decimal("5000"), Decimal("0")) == Decimal("0.00")
