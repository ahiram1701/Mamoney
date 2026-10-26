"""Cotizaciones de acciones, ETFs y cripto.

Fuente principal: el endpoint público de gráficas de Yahoo Finance (sin clave), que cubre
acciones y ETFs de EE. UU. y cripto (`BTC-USD`) con historial diario. Respaldo para cripto:
el precio spot público de Coinbase.
"""

import datetime as dt
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from mamoney import __version__
from mamoney.models import SecurityKind

log = logging.getLogger(__name__)

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"
COINBASE_SPOT = "https://api.coinbase.com/v2/prices/{pair}/spot"

KIND_BY_YAHOO_TYPE = {
    "EQUITY": SecurityKind.stock,
    "ETF": SecurityKind.etf,
    "CRYPTOCURRENCY": SecurityKind.crypto,
    "MUTUALFUND": SecurityKind.fund,
}


class QuoteError(LookupError):
    pass


@dataclass
class Quote:
    symbol: str
    price: float
    currency: str
    name: str | None
    kind: SecurityKind
    source: str


def normalize_symbol(symbol: str, kind: SecurityKind | None = None) -> str:
    """Notación de Yahoo: mayúsculas y, en cripto, el par en dólares (`btc` -> `BTC-USD`)."""
    value = symbol.strip().upper()
    if kind == SecurityKind.crypto and "-" not in value:
        return f"{value}-USD"
    return value


def _client(client: httpx.Client | None) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    headers = {"User-Agent": f"Mozilla/5.0 (Mamoney/{__version__})"}
    return httpx.Client(timeout=15, headers=headers, follow_redirects=True), True


def _chart(http: httpx.Client, symbol: str, params: dict[str, Any]) -> dict[str, Any]:
    resp = http.get(YAHOO_CHART.format(symbol=symbol), params=params)
    if resp.status_code == 404:
        raise QuoteError(f"No se encontró el símbolo {symbol}")
    resp.raise_for_status()
    result = (resp.json().get("chart") or {}).get("result") or []
    if not result:
        raise QuoteError(f"No hay datos para {symbol}")
    return dict(result[0])


def fetch_quote(symbol: str, client: httpx.Client | None = None) -> Quote:
    http, own = _client(client)
    try:
        try:
            meta = _chart(http, symbol, {"range": "1d", "interval": "1d"})["meta"]
            price = meta.get("regularMarketPrice")
            if not price:
                raise QuoteError(f"Yahoo no devolvió precio para {symbol}")
            return Quote(
                symbol=symbol,
                price=float(price),
                currency=str(meta.get("currency") or "USD").upper(),
                name=meta.get("longName") or meta.get("shortName"),
                kind=KIND_BY_YAHOO_TYPE.get(str(meta.get("instrumentType")), SecurityKind.other),
                source="yahoo",
            )
        except (httpx.HTTPError, QuoteError, ValueError, KeyError) as exc:
            if not symbol.endswith("-USD"):
                raise QuoteError(str(exc)) from exc
            log.info("Yahoo falló para %s (%s); se usa Coinbase", symbol, exc)
            resp = http.get(COINBASE_SPOT.format(pair=symbol))
            if resp.status_code != 200:
                raise QuoteError(f"No se encontró la cripto {symbol}") from exc
            amount = float(resp.json()["data"]["amount"])
            return Quote(symbol, amount, "USD", None, SecurityKind.crypto, "coinbase")
    finally:
        if own:
            http.close()


def fetch_history(
    symbol: str, since: dt.date, client: httpx.Client | None = None
) -> list[tuple[dt.date, float]]:
    """Cierres diarios desde `since` hasta hoy."""
    http, own = _client(client)
    start = dt.datetime.combine(since - dt.timedelta(days=7), dt.time(), tzinfo=dt.UTC)
    try:
        data = _chart(
            http,
            symbol,
            {
                "period1": int(start.timestamp()),
                "period2": int(dt.datetime.now(dt.UTC).timestamp()),
                "interval": "1d",
            },
        )
    finally:
        if own:
            http.close()
    stamps = data.get("timestamp") or []
    closes = (((data.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    history: dict[dt.date, float] = {}
    for stamp, close in zip(stamps, closes, strict=False):
        if close:
            history[dt.datetime.fromtimestamp(stamp, dt.UTC).date()] = float(close)
    return sorted(history.items())


def search(query: str, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Busca acciones, ETFs, fondos y cripto por nombre o símbolo."""
    http, own = _client(client)
    try:
        resp = http.get(YAHOO_SEARCH, params={"q": query, "quotesCount": 8, "newsCount": 0})
        resp.raise_for_status()
        quotes = resp.json().get("quotes") or []
    finally:
        if own:
            http.close()
    results = []
    for q in quotes:
        kind = KIND_BY_YAHOO_TYPE.get(str(q.get("quoteType")))
        if kind is None or not q.get("symbol"):
            continue
        results.append(
            {
                "symbol": q["symbol"],
                "name": q.get("longname") or q.get("shortname"),
                "kind": kind,
                "exchange": q.get("exchDisp") or q.get("exchange"),
            }
        )
    return results
