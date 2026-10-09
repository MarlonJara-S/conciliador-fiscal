from decimal import Decimal
from typing import Self

from pydantic import BaseModel, Field, model_validator

from conciliador_fiscal.invoices.domain.nit import nit_check_digit

NIT_ID_TYPE = "31"  # DIAN document type code for NIT


class InvoiceLine(BaseModel):
    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(ge=0)


class Party(BaseModel):
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
