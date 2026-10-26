"""Modelo de datos. Todos los montos se guardan en la moneda original del registro."""

import datetime as dt
from enum import StrEnum

from sqlmodel import Field, SQLModel


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Frequency(StrEnum):
    once = "once"
    weekly = "weekly"
    biweekly = "biweekly"  # quincenal: días 15 y último de cada mes
    monthly = "monthly"
    bimonthly = "bimonthly"
    quarterly = "quarterly"
    semiannual = "semiannual"
    annual = "annual"


class AssetType(StrEnum):
    cash = "cash"
    bank = "bank"
    investment = "investment"
    crypto = "crypto"
    retirement = "retirement"
    real_estate = "real_estate"
    vehicle = "vehicle"
    business = "business"
    receivable = "receivable"
    mortgage = "mortgage"
    credit_card = "credit_card"
    loan = "loan"
    other = "other"


class Liquidity(StrEnum):
    immediate = "immediate"
    short = "short"
    long = "long"
    illiquid = "illiquid"


class IncomeType(StrEnum):
    salary = "salary"
    freelance = "freelance"
    business = "business"
    rent = "rent"
    dividends = "dividends"
    interest = "interest"
    royalties = "royalties"
    sale = "sale"
    pension = "pension"
    other = "other"


class ExpenseCategory(StrEnum):
    housing = "housing"
    utilities = "utilities"
    insurance = "insurance"
    subscriptions = "subscriptions"
    transport = "transport"
    education = "education"
    health = "health"
    debt = "debt"
    taxes = "taxes"
    other = "other"


class AssetBase(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    type: AssetType
    is_liability: bool = False
    currency: str = Field(default="MXN", min_length=3, max_length=8)
    liquidity: Liquidity = Liquidity.immediate
    institution: str | None = Field(default=None, max_length=120)
    notes: str | None = None
    archived: bool = False
    # Cuenta de inversión con posiciones: su valor se calcula con operaciones y precios.
    tracks_positions: bool = False


class Asset(AssetBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: dt.datetime = Field(default_factory=_now)


class AssetValuationBase(SQLModel):
    date: dt.date
    value: float = Field(ge=0)
    notes: str | None = None


class AssetValuation(AssetValuationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True, ondelete="CASCADE")


class IncomeSourceBase(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    type: IncomeType
    is_passive: bool = False
    currency: str = Field(default="MXN", min_length=3, max_length=8)
    frequency: Frequency = Frequency.monthly
    expected_amount: float = Field(default=0, ge=0)
    asset_id: int | None = Field(default=None, foreign_key="asset.id", ondelete="SET NULL")
    active: bool = True
    notes: str | None = None


class IncomeSource(IncomeSourceBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: dt.datetime = Field(default_factory=_now)


class IncomeEntryBase(SQLModel):
    date: dt.date
    gross_amount: float = Field(ge=0)
    tax_withheld: float = Field(default=0, ge=0)
    notes: str | None = None


class IncomeEntry(IncomeEntryBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="incomesource.id", index=True, ondelete="CASCADE")

    @property
    def net_amount(self) -> float:
        return self.gross_amount - self.tax_withheld


class FixedExpenseBase(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    category: ExpenseCategory
    amount: float = Field(ge=0)
    currency: str = Field(default="MXN", min_length=3, max_length=8)
    frequency: Frequency = Frequency.monthly
    due_day: int = Field(default=1, ge=1, le=31)
    start_date: dt.date
    end_date: dt.date | None = None
    payment_asset_id: int | None = Field(default=None, foreign_key="asset.id", ondelete="SET NULL")
    active: bool = True
    notes: str | None = None


class FixedExpense(FixedExpenseBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: dt.datetime = Field(default_factory=_now)


class ExpensePaymentBase(SQLModel):
    due_date: dt.date
    paid_date: dt.date
    amount: float = Field(ge=0)
    notes: str | None = None


class ExpensePayment(ExpensePaymentBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    expense_id: int = Field(foreign_key="fixedexpense.id", index=True, ondelete="CASCADE")


class FxRate(SQLModel, table=True):
    """Cuántos MXN vale una unidad de `currency` en `date`."""

    id: int | None = Field(default=None, primary_key=True)
    date: dt.date = Field(index=True)
    currency: str = Field(index=True, max_length=8)
    rate_to_base: float = Field(gt=0)
    source: str = "manual"


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True, max_length=64)
    value: str


class SecurityKind(StrEnum):
    stock = "stock"
    etf = "etf"
    crypto = "crypto"
    fund = "fund"
    other = "other"


class TradeSide(StrEnum):
    buy = "buy"
    sell = "sell"
    # "En esta fecha tengo exactamente `quantity` títulos" (sin detallar compras o ventas).
    balance = "balance"


class Security(SQLModel, table=True):
    """Instrumento cotizado. `symbol` usa la notación de Yahoo Finance (AAPL, VOO, BTC-USD)."""

    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, unique=True, max_length=24)
    name: str | None = Field(default=None, max_length=160)
    kind: SecurityKind = SecurityKind.stock
    currency: str = Field(default="USD", max_length=8)
    last_price: float | None = None
    price_at: dt.datetime | None = None
    price_source: str | None = Field(default=None, max_length=32)


class SecurityPrice(SQLModel, table=True):
    """Precio de cierre diario, para reconstruir el valor histórico de las posiciones."""

    id: int | None = Field(default=None, primary_key=True)
    security_id: int = Field(foreign_key="security.id", index=True, ondelete="CASCADE")
    date: dt.date = Field(index=True)
    close: float = Field(gt=0)


class TradeBase(SQLModel):
    date: dt.date
    side: TradeSide = TradeSide.buy
    quantity: float = Field(ge=0)  # 0 solo tiene sentido en un saldo ("ya no tengo")
    # En un saldo es opcional: sin precio, el costo es el precio de mercado de esa fecha.
    price: float | None = Field(default=None, ge=0)
    fee: float = Field(default=0, ge=0)
    notes: str | None = None


class Trade(TradeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True, ondelete="CASCADE")
    security_id: int = Field(foreign_key="security.id", index=True, ondelete="RESTRICT")
