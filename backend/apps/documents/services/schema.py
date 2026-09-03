"""Tool schema for extraction (PROJECT_SPECS §5) and the Pydantic parse of the model's output.
Every numeric field is a STRING in the schema and parsed to Decimal here — never float."""

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

MONEY = {"type": "string", "description": "Decimal digits as a string, e.g. '1234.56'"}
STR = {"type": "string"}
BOOL = {"type": "boolean"}


def _obj(props: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props),
        "additionalProperties": False,
    }


INVOICE_TOOL: dict[str, Any] = {
    "name": "record_invoice",
    "description": "Record the extracted fields of one GST invoice.",
    "strict": True,
    "input_schema": _obj(
        {
            "supplier": _obj({"name": STR, "gstin": STR, "address": STR, "state_code": STR}),
            "recipient": _obj({"name": STR, "gstin": STR, "address": STR, "state_code": STR}),
            "invoice": _obj(
                {
                    "number": STR,
                    "date": STR,
                    "due_date": STR,
                    "irn": STR,
                    "has_qr": BOOL,
                    "place_of_supply": STR,
                    "is_reverse_charge": BOOL,
                    "payment_terms": STR,
                    "currency": STR,
                }
            ),
            "lines": {
                "type": "array",
                "items": _obj(
                    {
                        "description": STR,
                        "hsn_sac": STR,
                        "quantity": MONEY,
                        "uom": STR,
                        "unit_price": MONEY,
                        "discount": MONEY,
                        "taxable_value": MONEY,
                        "rate": MONEY,
                        "cgst": MONEY,
                        "sgst": MONEY,
                        "igst": MONEY,
                        "cess": MONEY,
                    }
                ),
            },
            "totals": _obj(
                {
                    "taxable_value": MONEY,
                    "cgst": MONEY,
                    "sgst": MONEY,
                    "igst": MONEY,
                    "cess": MONEY,
                    "round_off": MONEY,
                    "total": MONEY,
                }
            ),
            "bank_details": _obj(
                {"bank_name": STR, "account_number": STR, "ifsc": STR, "upi_id": STR}
            ),
            "notes": STR,
            "field_confidence": {
                "type": "object",
                "description": "dotted field path -> confidence 0..1",
                "additionalProperties": {"type": "number"},
            },
        }
    ),
}


def to_decimal(value: str, *, default: Decimal | None = Decimal("0")) -> Decimal | None:
    s = (value or "").strip().replace(",", "").replace("₹", "")
    if not s:
        return default
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"not a decimal: {value!r}") from exc


class Money(BaseModel):
    @field_validator("*", mode="before")
    @classmethod
    def _coerce(cls, v: Any, info: Any) -> Any:
        if isinstance(v, str) and cls.model_fields[info.field_name].annotation in (
            Decimal,
            Decimal | None,
        ):
            return to_decimal(v)
        if isinstance(v, float):
            raise ValueError("floats are not accepted for money")
        return v


class Supplier(BaseModel):
    name: str = ""
    gstin: str = ""
    address: str = ""
    state_code: str = ""


class InvoiceHeader(BaseModel):
    number: str = ""
    date: str = ""
    due_date: str = ""
    irn: str = ""
    has_qr: bool = False
    place_of_supply: str = ""
    is_reverse_charge: bool = False
    payment_terms: str = ""
    currency: str = "INR"


class Line(Money):
    description: str = ""
    hsn_sac: str = ""
    quantity: Decimal = Decimal("1")
    uom: str = ""
    unit_price: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    taxable_value: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")
    cess: Decimal = Decimal("0")


class Totals(Money):
    taxable_value: Decimal = Decimal("0")
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")
    cess: Decimal = Decimal("0")
    round_off: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class BankDetails(BaseModel):
    bank_name: str = ""
    account_number: str = ""
    ifsc: str = ""
    upi_id: str = ""


class ExtractedInvoice(BaseModel):
    supplier: Supplier
    recipient: Supplier
    invoice: InvoiceHeader
    lines: list[Line] = Field(default_factory=list)
    totals: Totals
    bank_details: BankDetails = Field(default_factory=BankDetails)
    notes: str = ""
    field_confidence: dict[str, float] = Field(default_factory=dict)

    @field_validator("field_confidence")
    @classmethod
    def _clamp(cls, v: dict[str, float]) -> dict[str, float]:
        return {k: min(1.0, max(0.0, float(c))) for k, c in v.items()}

    def dump(self) -> dict[str, Any]:
        """JSON-safe: Decimals as strings."""
        return self.model_dump(mode="json")
