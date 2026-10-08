NIT_WEIGHTS = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def nit_check_digit(nit: str) -> int:
    """Return the DIAN verification digit (DV) for a NIT."""
    total = 0

    for digit, weight in zip(reversed(nit), NIT_WEIGHTS, strict=False):
        total += int(digit) * weight

    remainder = total % 11
    if remainder in (0, 1):
        return remainder
    return 11 - remainder
