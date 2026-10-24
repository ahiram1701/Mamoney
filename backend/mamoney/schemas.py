"""Esquemas de entrada/salida de la API."""

import datetime as dt
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, create_model, field_validator
from sqlmodel import SQLModel

from mamoney.models import (
    AssetBase,
    AssetValuationBase,
    ExpensePaymentBase,
    FixedExpenseBase,
    IncomeEntryBase,
    IncomeSourceBase,
)


def partial(model: type[SQLModel], name: str) -> type[BaseModel]:
    """Versión con todos los campos opcionales, para PATCH."""
    fields: dict[str, Any] = {
        field_name: (info.annotation | None, None)  # type: ignore[operator]
        for field_name, info in model.model_fields.items()
    }
    return create_model(name, **fields)


class _UpperCurrency(BaseModel):
    @field_validator("currency", check_fields=False)
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class AssetCreate(_UpperCurrency, AssetBase):
    initial_value: float | None = None
    initial_date: dt.date | None = None


class AssetRead(AssetBase):
    id: int


class ValuationCreate(AssetValuationBase):
    pass


class ValuationRead(AssetValuationBase):
    id: int
    asset_id: int


class IncomeSourceCreate(_UpperCurrency, IncomeSourceBase):
    pass


class IncomeSourceRead(IncomeSourceBase):
    id: int


class IncomeEntryCreate(IncomeEntryBase):
    pass


class IncomeEntryRead(IncomeEntryBase):
    id: int
    source_id: int
    net_amount: float


class FixedExpenseCreate(_UpperCurrency, FixedExpenseBase):
    pass


class FixedExpenseRead(FixedExpenseBase):
    id: int


class PaymentCreate(ExpensePaymentBase):
    expense_id: int


class PaymentRead(ExpensePaymentBase):
    id: int
    expense_id: int


class FxRateCreate(BaseModel):
    currency: str
    date: dt.date
    rate_to_base: float

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class SettingsUpdate(BaseModel):
    currencies: list[str] | None = None
    allowed_logins: list[str] | None = None
    projection_annual_return_pct: float | None = None


class PinUpdate(BaseModel):
    pin: str | None = None  # None o "" desactiva el PIN


class PinLogin(BaseModel):
    pin: str


# Modelos PATCH generados: para mypy son BaseModel genéricos.
if TYPE_CHECKING:
    AssetUpdate = BaseModel
    ValuationUpdate = BaseModel
    IncomeSourceUpdate = BaseModel
    IncomeEntryUpdate = BaseModel
    FixedExpenseUpdate = BaseModel
else:
    AssetUpdate = partial(AssetBase, "AssetUpdate")
    ValuationUpdate = partial(AssetValuationBase, "ValuationUpdate")
    IncomeSourceUpdate = partial(IncomeSourceBase, "IncomeSourceUpdate")
    IncomeEntryUpdate = partial(IncomeEntryBase, "IncomeEntryUpdate")
    FixedExpenseUpdate = partial(FixedExpenseBase, "FixedExpenseUpdate")
