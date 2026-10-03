from decimal import ROUND_HALF_UP, Decimal


def calculate_vat(subtotal: Decimal, rate: Decimal) -> Decimal:
    """Return the VAT amount rounded to 2 decimals."""
    vat = subtotal * rate

    return vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
