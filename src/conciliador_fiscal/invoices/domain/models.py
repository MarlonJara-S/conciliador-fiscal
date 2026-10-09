from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from conciliador_fiscal.invoices.domain.nit import nit_check_digit

NIT_ID_TYPE = "31"  # DIAN document type code for NIT
CUFE_PATTERN = r"^[0-9a-fA-F]{96}$"  # SHA-384 hash in hexadecimal
CURRENCY_PATTERN = r"^[A-Z]{3}$"  # ISO 4217 code, e.g. "COP"
MAX_TAX_RATE = Decimal("100")


class DomainModel(BaseModel):
    """Base for every invoice model: validated once, never changed afterwards."""

    model_config = ConfigDict(frozen=True)


class InvoiceLine(DomainModel):
    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(ge=0)


class Party(DomainModel):
    name: str = Field(min_length=1)
    id_type: str
    id_number: str = Field(min_length=1)
    check_digit: int | None = None

    @model_validator(mode="after")
    def check_nit_digit(self) -> Self:
        if self.id_type != NIT_ID_TYPE:
            return self
        if self.check_digit is None:
            raise ValueError(f"NIT {self.id_number!r} requires a check digit")
        expected = nit_check_digit(self.id_number)
        if self.check_digit != expected:
            raise ValueError(
                f"Check digit {self.check_digit} does not match NIT {self.id_number!r} "
                f"(expected {expected})"
            )
        return self


class TaxSubtotal(DomainModel):
    """One tax of the invoice, e.g. VAT at 19% (cac:TaxTotal at invoice level)."""

    tax_id: str = Field(min_length=1)  # DIAN tax code, e.g. "01" for IVA
    tax_name: str = Field(min_length=1)
    taxable_amount: Decimal = Field(ge=0)
    rate: Decimal = Field(ge=0, le=MAX_TAX_RATE)  # percentage, e.g. 19.00
    tax_amount: Decimal = Field(ge=0)


class MonetaryTotals(DomainModel):
    """Invoice totals (cac:LegalMonetaryTotal)."""

    line_extension_amount: Decimal = Field(ge=0)  # sum of the lines, before taxes
    tax_exclusive_amount: Decimal = Field(ge=0)  # base on which taxes are calculated
    tax_inclusive_amount: Decimal = Field(ge=0)  # total including taxes
    payable_amount: Decimal = Field(ge=0)  # what the customer has to pay


class Invoice(DomainModel):
    """An electronic invoice (UBL 2.1), as extracted from the AttachedDocument."""

    cufe: str = Field(pattern=CUFE_PATTERN)
    number: str = Field(min_length=1)
    issue_date: date
    currency: str = Field(pattern=CURRENCY_PATTERN)
    supplier: Party
    customer: Party
    lines: list[InvoiceLine] = Field(min_length=1)
    taxes: list[TaxSubtotal]
    totals: MonetaryTotals
