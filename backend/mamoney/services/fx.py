"""Tipos de cambio a la moneda base (MXN)."""

import bisect
import logging
from collections import defaultdict
from datetime import date

import httpx
from sqlmodel import Session, select

from mamoney.config import get_config
from mamoney.models import FxRate

log = logging.getLogger(__name__)

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"


class MissingRateError(LookupError):
    def __init__(self, currency: str) -> None:
        super().__init__(f"No hay tipo de cambio registrado para {currency}")
        self.currency = currency


class FxTable:
    """Tabla en memoria de tasas históricas; resuelve la tasa vigente en una fecha.

    Para una fecha se usa la tasa más reciente anterior o igual; si la fecha es anterior
    a todo el historial, se usa la primera tasa conocida.
    """

    def __init__(self, rates: list[FxRate], base: str | None = None) -> None:
        self.base = base or get_config().base_currency
        by_currency: dict[str, list[tuple[date, float]]] = defaultdict(list)
        for rate in rates:
            by_currency[rate.currency.upper()].append((rate.date, rate.rate_to_base))
        self._dates: dict[str, list[date]] = {}
        self._values: dict[str, list[float]] = {}
        for currency, items in by_currency.items():
            items.sort()
            self._dates[currency] = [d for d, _ in items]
            self._values[currency] = [v for _, v in items]

    @classmethod
    def load(cls, session: Session) -> "FxTable":
        return cls(list(session.exec(select(FxRate)).all()))

    def currencies(self) -> set[str]:
        return set(self._dates)

    def rate(self, currency: str, on: date) -> float:
        currency = currency.upper()
        if currency == self.base:
            return 1.0
        dates = self._dates.get(currency)
        if not dates:
            raise MissingRateError(currency)
        idx = bisect.bisect_right(dates, on) - 1
        return self._values[currency][max(idx, 0)]

    def convert(self, amount: float, currency: str, on: date) -> float:
        return amount * self.rate(currency, on)


def upsert_rate(
    session: Session, currency: str, on: date, rate: float, source: str = "manual"
) -> FxRate:
    currency = currency.upper()
    existing = session.exec(
        select(FxRate).where(FxRate.currency == currency, FxRate.date == on)
    ).first()
    if existing:
        existing.rate_to_base = rate
        existing.source = source
        record = existing
    else:
        record = FxRate(currency=currency, date=on, rate_to_base=rate, source=source)
    session.add(record)
    return record


def fetch_latest(currencies: set[str], client: httpx.Client | None = None) -> dict[str, float]:
    """Consulta Frankfurter (BCE) y devuelve MXN por unidad de cada moneda soportada."""
    base = get_config().base_currency
    wanted = sorted(c.upper() for c in currencies if c.upper() != base)
    if not wanted:
        return {}
    own_client = client is None
    http = client or httpx.Client(timeout=10)
    try:
        resp = http.get(FRANKFURTER_URL, params={"base": base, "symbols": ",".join(wanted)})
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own_client:
            http.close()
    # La API da unidades de moneda extranjera por 1 MXN; invertimos.
    return {cur: 1 / value for cur, value in data.get("rates", {}).items() if value}


def refresh_rates(
    session: Session, currencies: set[str], client: httpx.Client | None = None
) -> int:
    try:
        rates = fetch_latest(currencies, client)
    except httpx.HTTPError as exc:
        log.warning("No se pudieron actualizar los tipos de cambio: %s", exc)
        return 0
    today = date.today()
    for currency, value in rates.items():
        upsert_rate(session, currency, today, value, source="frankfurter")
    session.commit()
    return len(rates)
