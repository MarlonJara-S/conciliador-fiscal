import pytest

from conciliador_fiscal.invoices.domain.nit import nit_check_digit


@pytest.mark.parametrize(
    ("nit", "expected"),
    [
        ("800197268", 4),  # DIAN
        ("890903938", 8),
    ],
)
def test_check_digit_matches_published_nits(nit: str, expected: int) -> None:
    assert nit_check_digit(nit) == expected
