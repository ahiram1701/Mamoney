import datetime as dt

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from mamoney.models import AssetValuation, SecurityKind, Trade, TradeSide
from mamoney.services import portfolio, quotes

TODAY = dt.date.today()


def _trade(
    day: int, side: TradeSide, qty: float, price: float, fee: float = 0, tid: int = 0
) -> Trade:
    return Trade(
        id=tid or day,
        asset_id=1,
        security_id=1,
        date=dt.date(2026, 1, day),
        side=side,
        quantity=qty,
        price=price,
        fee=fee,
    )


def test_average_cost_and_realized_gain() -> None:
    book = portfolio.apply_trades(
        [
            _trade(2, TradeSide.buy, 10, 100, fee=1),
            _trade(5, TradeSide.buy, 10, 120),
            _trade(9, TradeSide.sell, 5, 150, fee=1),
        ]
    )
    pos = book.positions[1]
    assert pos.quantity == 15
    assert pos.avg_cost == pytest.approx(2201 / 20)
    assert pos.realized == pytest.approx(5 * 150 - 1 - 5 * 2201 / 20)
    assert pos.cost == pytest.approx(2201 - 5 * 2201 / 20)


def test_selling_everything_resets_cost() -> None:
    book = portfolio.apply_trades(
        [_trade(2, TradeSide.buy, 2, 50), _trade(3, TradeSide.sell, 2, 70)]
    )
    assert book.positions[1].quantity == 0 and book.positions[1].cost == 0
    assert book.positions[1].realized == pytest.approx(40)


def test_overselling_is_rejected() -> None:
    with pytest.raises(portfolio.PortfolioError, match="supera"):
        portfolio.apply_trades([_trade(2, TradeSide.buy, 1, 10), _trade(3, TradeSide.sell, 2, 10)])


def test_normalize_symbol() -> None:
    assert quotes.normalize_symbol(" btc ", SecurityKind.crypto) == "BTC-USD"
    assert quotes.normalize_symbol("eth-usd", SecurityKind.crypto) == "ETH-USD"
    assert quotes.normalize_symbol("voo") == "VOO"


def test_valuation_dates_cover_first_trade_month_ends_and_today() -> None:
    dates = portfolio._valuation_dates(dt.date(2026, 1, 15), dt.date(2026, 3, 10))
    assert dates == [
        dt.date(2026, 1, 15),
        dt.date(2026, 1, 31),
        dt.date(2026, 2, 28),
        dt.date(2026, 3, 10),
    ]


# --- Yahoo / Coinbase simulados ---------------------------------------------------------


def _yahoo_handler(
    prices: dict[str, float], history: dict[str, list[tuple[dt.date, float]]] | None = None
):  # type: ignore[no-untyped-def]
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "coinbase" in url:
            pair = request.url.path.split("/")[-2]
            if pair in prices:
                return httpx.Response(200, json={"data": {"amount": str(prices[pair])}})
            return httpx.Response(404)
        if "/search" in url:
            return httpx.Response(
                200,
                json={
                    "quotes": [
                        {"symbol": "VOO", "quoteType": "ETF", "longname": "Vanguard S&P 500 ETF"},
                        {"symbol": "X", "quoteType": "OPTION"},
                    ]
                },
            )
        symbol = request.url.path.rsplit("/", 1)[-1]
        if symbol not in prices:
            return httpx.Response(404, json={"chart": {"result": None}})
        series = (history or {}).get(symbol, [])
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "regularMarketPrice": prices[symbol],
                                "currency": "USD",
                                "longName": f"{symbol} Inc.",
                                "instrumentType": "CRYPTOCURRENCY"
                                if symbol.endswith("-USD")
                                else "EQUITY",
                            },
                            "timestamp": [
                                int(dt.datetime.combine(d, dt.time(14), tzinfo=dt.UTC).timestamp())
                                for d, _ in series
                            ],
                            "indicators": {"quote": [{"close": [c for _, c in series]}]},
                        }
                    ]
                }
            },
        )

    return handler


@pytest.fixture
def market(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    state = {"prices": {"AAPL": 200.0, "BTC-USD": 80000.0}, "history": {}}

    def client() -> httpx.Client:
        return httpx.Client(
            transport=httpx.MockTransport(_yahoo_handler(state["prices"], state["history"]))
        )

    real_quote, real_history, real_search = quotes.fetch_quote, quotes.fetch_history, quotes.search
    monkeypatch.setattr(quotes, "fetch_quote", lambda s, c=None: real_quote(s, client()))
    monkeypatch.setattr(
        quotes, "fetch_history", lambda s, since, c=None: real_history(s, since, client())
    )
    monkeypatch.setattr(quotes, "search", lambda q, c=None: real_search(q, client()))
    return state


def test_quote_parsing(market) -> None:  # type: ignore[no-untyped-def]
    q = quotes.fetch_quote("AAPL")
    assert q.price == 200 and q.kind == SecurityKind.stock and q.source == "yahoo"
    with pytest.raises(quotes.QuoteError):
        quotes.fetch_quote("NOPE")


def test_crypto_falls_back_to_coinbase() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "yahoo" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, json={"data": {"amount": "150.5", "currency": "USD"}})

    q = quotes.fetch_quote("SOL-USD", httpx.Client(transport=httpx.MockTransport(handler)))
    assert q.price == 150.5 and q.source == "coinbase" and q.kind == SecurityKind.crypto


def test_search_filters_supported_types(market) -> None:  # type: ignore[no-untyped-def]
    results = quotes.search("vanguard")
    assert [r["symbol"] for r in results] == ["VOO"]
    assert results[0]["kind"] == SecurityKind.etf


def _account(client: TestClient, currency: str = "USD") -> int:
    r = client.post(
        "/api/assets",
        json={
            "name": "Broker",
            "type": "investment",
            "currency": currency,
            "tracks_positions": True,
        },
    )
    return int(r.json()["id"])


def test_trade_flow_values_account_automatically(
    client: TestClient, session: Session, market
) -> None:  # type: ignore[no-untyped-def]
    start = TODAY - dt.timedelta(days=45)
    market["history"]["AAPL"] = [(start + dt.timedelta(days=i), 150.0 + i) for i in range(46)]
    client.post("/api/fx/rates", json={"currency": "USD", "date": "2020-01-01", "rate_to_base": 18})
    account = _account(client)

    r = client.post(
        "/api/portfolio/trades",
        json={
            "asset_id": account,
            "symbol": "aapl",
            "date": start.isoformat(),
            "quantity": 10,
            "price": 150,
            "fee": 5,
        },
    )
    assert r.status_code == 201, r.text

    report = client.get("/api/portfolio/positions").json()
    pos = report["positions"][0]
    assert pos["symbol"] == "AAPL" and pos["quantity"] == 10
    assert pos["value"] == 2000 and pos["cost"] == 1505
    assert pos["gain"] == 495 and pos["weight_pct"] == 100

    vals = session.exec(select(AssetValuation).where(AssetValuation.asset_id == account)).all()
    by_date = {v.date: v.value for v in vals}
    assert by_date[start] == 1500  # cierre del día de la compra
    assert by_date[TODAY] == 2000  # precio en vivo
    assert len(by_date) >= 3  # incluye al menos un cierre de mes
    assert all(v.notes == portfolio.AUTO_NOTE for v in vals)

    # La cuenta aparece en el patrimonio sin cambios en el resto de la app.
    assert report["value_base"] == 2000 * 18
    assert client.get("/api/analytics/summary").json()["net_worth"] == 2000 * 18


def test_manual_valuation_rejected_for_tracked_account(client: TestClient, market) -> None:  # type: ignore[no-untyped-def]
    account = _account(client)
    r = client.post(f"/api/assets/{account}/valuations", json={"date": "2026-01-01", "value": 1})
    assert r.status_code == 409


def test_oversell_and_unsafe_delete_are_rejected(client: TestClient, market) -> None:  # type: ignore[no-untyped-def]
    account = _account(client)
    day = (TODAY - dt.timedelta(days=3)).isoformat()
    buy = client.post(
        "/api/portfolio/trades",
        json={
            "asset_id": account,
            "symbol": "btc",
            "kind": "crypto",
            "date": day,
            "quantity": 0.5,
            "price": 70000,
        },
    ).json()
    assert buy["symbol"] == "BTC-USD"
    oversell = {
        "asset_id": account,
        "symbol": "BTC-USD",
        "date": day,
        "side": "sell",
        "quantity": 1,
        "price": 1,
    }
    assert client.post("/api/portfolio/trades", json=oversell).status_code == 422
    oversell["quantity"] = 0.2
    assert client.post("/api/portfolio/trades", json=oversell).status_code == 201
    assert client.delete(f"/api/portfolio/trades/{buy['id']}").status_code == 422


def test_unknown_symbol_and_untracked_account(client: TestClient, market) -> None:  # type: ignore[no-untyped-def]
    account = _account(client)
    trade = {
        "asset_id": account,
        "symbol": "NOPE",
        "date": TODAY.isoformat(),
        "quantity": 1,
        "price": 1,
    }
    assert client.post("/api/portfolio/trades", json=trade).status_code == 422
    plain = client.post("/api/assets", json={"name": "Banco", "type": "bank"}).json()["id"]
    trade.update(asset_id=plain, symbol="AAPL")
    assert client.post("/api/portfolio/trades", json=trade).status_code == 409


def test_refresh_updates_prices_and_mxn_account(client: TestClient, market) -> None:  # type: ignore[no-untyped-def]
    client.post("/api/fx/rates", json={"currency": "USD", "date": "2020-01-01", "rate_to_base": 20})
    account = _account(client, currency="MXN")  # cuenta en pesos con acciones en dólares
    client.post(
        "/api/portfolio/trades",
        json={
            "asset_id": account,
            "symbol": "AAPL",
            "date": TODAY.isoformat(),
            "quantity": 2,
            "price": 200,
        },
    )
    market["prices"]["AAPL"] = 250.0
    assert client.post("/api/portfolio/refresh").json() == {"updated": 1, "failed": 0}
    row = client.get("/api/analytics/assets").json()
    broker = next(r for r in row if r["id"] == account)
    assert broker["value"] == 2 * 250 * 20
