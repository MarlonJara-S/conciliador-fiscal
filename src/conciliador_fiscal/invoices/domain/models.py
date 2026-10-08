from decimal import Decimal

from pydantic import BaseModel, Field


class InvoiceLine(BaseModel):
    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    line_total: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(ge=0)
