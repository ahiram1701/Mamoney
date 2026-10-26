"""Posiciones de inversión: costo promedio, ganancias y valuación automática de la cuenta.

Una cuenta (`Asset.tracks_positions`) no se valúa a mano: su valor es la suma de títulos por
precio de mercado. Tras cada operación o actualización de precios se regeneran sus
valuaciones automáticas (fecha de la primera compra, cierre de cada mes y hoy), así el
patrimonio, su historial y los análisis existentes la incluyen sin cambios.
"""

import bisect
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlmodel import Session, col, delete, select

from mamoney.models import (
    Asset,
    AssetValuation,
    Security,
    SecurityKind,
    SecurityPrice,
    Trade,
    TradeSide,
)
from mamoney.services import quotes
from mamoney.services.fx import FxTable, MissingRateError
from mamoney.services.scheduling import add_months, clamp_day

log = logging.getLogger(__name__)

AUTO_NOTE = "auto: posiciones"
EPSILON = 1e-9


class PortfolioError(ValueError):
    pass


@dataclass
class Position:
    security_id: int
    quantity: float = 0.0
    cost: float = 0.0  # costo total de los títulos en cartera (método de costo promedio)
    realized: float = 0.0
    fees: float = 0.0
    first_date: dt.date | None = None

    @property
    def avg_cost(self) -> float:
        return self.cost / self.quantity if self.quantity > EPSILON else 0.0


@dataclass
class Book:
    """Resultado de aplicar las operaciones en orden cronológico."""

    positions: dict[int, Position] = field(default_factory=dict)


CostFor = Callable[[Trade], float | None]


def apply_trades(
    trades: list[Trade], until: dt.date | None = None, cost_for: CostFor | None = None
) -> Book:
    """Aplica las operaciones en orden.

    `cost_for(trade)` da el costo por título de un saldo capturado sin precio (normalmente el
    cierre de mercado de esa fecha). Sin él, esos títulos entran con costo 0.
    """
    book = Book()
    # Mismo día: por orden de captura; una operación aún sin guardar (sin id) va al final.
    ordered = sorted(trades, key=lambda t: (t.date, t.id if t.id is not None else float("inf")))
    for trade in ordered:
        if until and trade.date > until:
            break
        pos = book.positions.setdefault(trade.security_id, Position(trade.security_id))
        pos.fees += trade.fee
        if pos.first_date is None:
            pos.first_date = trade.date
        if trade.side == TradeSide.balance:
            delta = trade.quantity - pos.quantity
            if delta > EPSILON:
                unit_cost = trade.price
                if unit_cost is None and cost_for is not None:
                    unit_cost = cost_for(trade)
                pos.cost += delta * (unit_cost or 0.0) + trade.fee
                pos.quantity = trade.quantity
            elif delta < -EPSILON:
                # Salen títulos sin venta: se descuentan al costo promedio, sin ganancia realizada.
                pos.cost -= pos.avg_cost * -delta
                pos.quantity = trade.quantity
            if pos.quantity < EPSILON:
                pos.quantity, pos.cost = 0.0, 0.0
        elif trade.side == TradeSide.buy:
            pos.quantity += trade.quantity
            pos.cost += trade.quantity * (trade.price or 0.0) + trade.fee
        else:
            if trade.quantity > pos.quantity + EPSILON:
                raise PortfolioError(
                    f"La venta del {trade.date.isoformat()} supera los títulos en cartera "
                    f"({pos.quantity:g})"
                )
            released = pos.avg_cost * trade.quantity
            pos.realized += trade.quantity * (trade.price or 0.0) - trade.fee - released
            pos.cost -= released
            pos.quantity -= trade.quantity
            if pos.quantity < EPSILON:
                pos.quantity, pos.cost = 0.0, 0.0
    return book


def local_date(moment: dt.datetime) -> dt.date:
    """Fecha en el calendario local; los instantes se guardan en UTC (a veces sin zona)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return moment.astimezone().date()


class PriceBook:
    """Precios históricos por instrumento; usa el cierre más reciente <= fecha."""

    def __init__(self, session: Session, security_ids: set[int]) -> None:
        self._dates: dict[int, list[dt.date]] = defaultdict(list)
        self._closes: dict[int, list[float]] = defaultdict(list)
        if security_ids:
            rows = session.exec(
                select(SecurityPrice)
                .where(col(SecurityPrice.security_id).in_(security_ids))
                .order_by(col(SecurityPrice.date))
            ).all()
            for row in rows:
                self._dates[row.security_id].append(row.date)
                self._closes[row.security_id].append(row.close)
        self._latest = {
            s.id: s
            for s in session.exec(select(Security).where(col(Security.id).in_(security_ids))).all()
        }

    def price(self, security_id: int, on: dt.date) -> float | None:
        sec = self._latest.get(security_id)
        if sec and sec.last_price and sec.price_at and local_date(sec.price_at) <= on:
            # El precio en vivo es más reciente que cualquier cierre guardado de esa fecha.
            dates = self._dates.get(security_id, [])
            if not dates or dates[-1] <= local_date(sec.price_at):
                return sec.last_price
        dates = self._dates.get(security_id, [])
        idx = bisect.bisect_right(dates, on) - 1
        if idx >= 0:
            return self._closes[security_id][idx]
        return None


def market_cost(prices: "PriceBook") -> CostFor:
    """Costo de un saldo sin precio: el cierre de mercado de su fecha."""
    return lambda trade: prices.price(trade.security_id, trade.date)


def _convert(fx: FxTable, amount: float, from_cur: str, to_cur: str, on: dt.date) -> float:
    if from_cur.upper() == to_cur.upper():
        return amount
    return amount * fx.rate(from_cur, on) / fx.rate(to_cur, on)


def account_trades(session: Session, asset_id: int) -> list[Trade]:
    return list(session.exec(select(Trade).where(Trade.asset_id == asset_id)).all())


def get_or_create_security(
    session: Session, symbol: str, kind: SecurityKind | None, client: httpx.Client | None = None
) -> Security:
    normalized = quotes.normalize_symbol(symbol, kind)
    existing = session.exec(select(Security).where(Security.symbol == normalized)).first()
    if existing:
        return existing
    try:
        quote = quotes.fetch_quote(normalized, client)
    except (quotes.QuoteError, httpx.HTTPError) as exc:
        raise PortfolioError(f"No se pudo validar el símbolo {normalized}: {exc}") from exc
    security = Security(
        symbol=normalized,
        name=quote.name,
        kind=kind or quote.kind,
        currency=quote.currency,
        last_price=quote.price,
        price_at=dt.datetime.now(dt.UTC),
        price_source=quote.source,
    )
    session.add(security)
    session.flush()
    return security


def ensure_history(
    session: Session, security: Security, since: dt.date, client: httpx.Client | None = None
) -> None:
    """Descarga los cierres diarios que falten desde `since` (tolerante a fallas de red)."""
    first = session.exec(
        select(col(SecurityPrice.date))
        .where(SecurityPrice.security_id == security.id)
        .order_by(col(SecurityPrice.date))
    ).first()
    if first is not None and first <= since:
        return
    try:
        history = quotes.fetch_history(security.symbol, since, client)
    except (quotes.QuoteError, httpx.HTTPError) as exc:
        log.warning("Sin historial para %s: %s", security.symbol, exc)
        return
    existing = set(
        session.exec(
            select(col(SecurityPrice.date)).where(SecurityPrice.security_id == security.id)
        ).all()
    )
    for day, close in history:
        if day not in existing:
            session.add(SecurityPrice(security_id=security.id, date=day, close=close))  # type: ignore[arg-type]


def _valuation_dates(first: dt.date, today: dt.date) -> list[dt.date]:
    dates = {first, today}
    year, month = first.year, first.month
    while True:
        month_end = clamp_day(year, month, 31)
        if month_end >= today:
            break
        if month_end > first:
            dates.add(month_end)
        year, month = add_months(year, month, 1)
    return sorted(dates)


def account_value(
    asset: Asset,
    trades: list[Trade],
    prices: PriceBook,
    securities: dict[int, Security],
    fx: FxTable,
    on: dt.date,
) -> float:
    book = apply_trades(trades, until=on, cost_for=market_cost(prices))
    total = 0.0
    for pos in book.positions.values():
        if pos.quantity < EPSILON:
            continue
        price = prices.price(pos.security_id, on)
        if price is None:
            price = pos.avg_cost  # sin precio aún: se valúa al costo
        sec = securities[pos.security_id]
        total += _convert(fx, pos.quantity * price, sec.currency, asset.currency, on)
    return total


def sync_account(session: Session, asset: Asset, today: dt.date | None = None) -> int:
    """Regenera las valuaciones automáticas de una cuenta con posiciones."""
    today = today or dt.date.today()
    trades = account_trades(session, asset.id)  # type: ignore[arg-type]
    session.exec(
        delete(AssetValuation).where(
            col(AssetValuation.asset_id) == asset.id, col(AssetValuation.notes) == AUTO_NOTE
        )
    )
    if not trades:
        session.commit()
        return 0
    ids = {t.security_id for t in trades}
    securities = {s.id: s for s in session.exec(select(Security).where(col(Security.id).in_(ids)))}
    prices = PriceBook(session, ids)
    fx = FxTable.load(session)
    first = min(t.date for t in trades)
    count = 0
    for day in _valuation_dates(first, today):
        try:
            value = account_value(asset, trades, prices, securities, fx, day)  # type: ignore[arg-type]
        except MissingRateError as exc:
            log.warning("Falta tipo de cambio %s para valuar %s", exc.currency, asset.name)
            continue
        manual = session.exec(
            select(AssetValuation).where(
                AssetValuation.asset_id == asset.id, AssetValuation.date == day
            )
        ).first()
        if manual:
            session.delete(manual)  # en cuentas con posiciones manda el cálculo
        session.add(
            AssetValuation(asset_id=asset.id, date=day, value=round(value, 2), notes=AUTO_NOTE)  # type: ignore[arg-type]
        )
        count += 1
    session.commit()
    return count


def refresh_prices(session: Session, client: httpx.Client | None = None) -> dict[str, int]:
    """Actualiza precios de los instrumentos con operaciones y recalcula las cuentas."""
    used = set(session.exec(select(Trade.security_id).distinct()).all())
    updated = failed = 0
    today = dt.date.today()
    for security in session.exec(select(Security).where(col(Security.id).in_(used))).all():
        try:
            quote = quotes.fetch_quote(security.symbol, client)
        except (quotes.QuoteError, httpx.HTTPError) as exc:
            log.warning("No se pudo cotizar %s: %s", security.symbol, exc)
            failed += 1
            continue
        security.last_price = quote.price
        security.price_at = dt.datetime.now(dt.UTC)
        security.price_source = quote.source
        if not security.name and quote.name:
            security.name = quote.name
        row = session.exec(
            select(SecurityPrice).where(
                SecurityPrice.security_id == security.id, SecurityPrice.date == today
            )
        ).first()
        if row:
            row.close = quote.price
        else:
            session.add(SecurityPrice(security_id=security.id, date=today, close=quote.price))  # type: ignore[arg-type]
        updated += 1
    session.commit()
    for asset in session.exec(select(Asset).where(col(Asset.tracks_positions))).all():
        sync_account(session, asset, today)
    return {"updated": updated, "failed": failed}


def positions_report(session: Session, asset_id: int | None = None) -> dict[str, Any]:
    """Posiciones abiertas con valor, costo y ganancias, en moneda del instrumento y en MXN."""
    query = select(Asset).where(col(Asset.tracks_positions))
    if asset_id is not None:
        query = query.where(Asset.id == asset_id)
    accounts = list(session.exec(query).all())
    fx = FxTable.load(session)
    today = dt.date.today()
    rows: list[dict[str, Any]] = []
    totals = {"value_base": 0.0, "cost_base": 0.0, "realized_base": 0.0}
    missing: set[str] = set()

    def to_base(amount: float, currency: str) -> float:
        try:
            return fx.convert(amount, currency, today)
        except MissingRateError as exc:
            missing.add(exc.currency)
            return 0.0

    for account in accounts:
        trades = account_trades(session, account.id)  # type: ignore[arg-type]
        if not trades:
            continue
        ids = {t.security_id for t in trades}
        prices = PriceBook(session, ids)
        book = apply_trades(trades, cost_for=market_cost(prices))
        securities = {
            s.id: s for s in session.exec(select(Security).where(col(Security.id).in_(ids)))
        }
        for pos in book.positions.values():
            sec = securities[pos.security_id]
            totals["realized_base"] += to_base(pos.realized, sec.currency)
            if pos.quantity < EPSILON:
                continue
            price = prices.price(pos.security_id, today)
            value = pos.quantity * price if price is not None else None
            gain = value - pos.cost if value is not None else None
            value_base = to_base(value if value is not None else pos.cost, sec.currency)
            cost_base = to_base(pos.cost, sec.currency)
            totals["value_base"] += value_base
            totals["cost_base"] += cost_base
            rows.append(
                {
                    "account_id": account.id,
                    "account": account.name,
                    "security_id": sec.id,
                    "symbol": sec.symbol,
                    "name": sec.name,
                    "kind": sec.kind,
                    "currency": sec.currency,
                    "quantity": pos.quantity,
                    "avg_cost": round(pos.avg_cost, 6),
                    "cost": round(pos.cost, 2),
                    "price": price,
                    "price_at": sec.price_at.isoformat() if sec.price_at else None,
                    "value": round(value, 2) if value is not None else None,
                    "gain": round(gain, 2) if gain is not None else None,
                    "gain_pct": round(gain / pos.cost * 100, 2)
                    if gain is not None and pos.cost
                    else None,
                    "realized": round(pos.realized, 2),
                    "value_base": round(value_base, 2),
                }
            )
    total_value = totals["value_base"]
    for row in rows:
        row["weight_pct"] = round(row["value_base"] / total_value * 100, 2) if total_value else None
    rows.sort(key=lambda r: -r["value_base"])
    unrealized = totals["value_base"] - totals["cost_base"]
    return {
        "positions": rows,
        "value_base": round(totals["value_base"], 2),
        "cost_base": round(totals["cost_base"], 2),
        "unrealized_base": round(unrealized, 2),
        "unrealized_pct": round(unrealized / totals["cost_base"] * 100, 2)
        if totals["cost_base"]
        else None,
        "realized_base": round(totals["realized_base"], 2),
        "missing_rates": sorted(missing),
    }
