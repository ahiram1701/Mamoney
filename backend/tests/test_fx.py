from datetime import date

import httpx
import pytest
from sqlmodel import Session, select

from mamoney.models import FxRate
from mamoney.services.fx import FxTable, MissingRateError, fetch_latest, refresh_rates


def _table() -> FxTable:
    return FxTable(
        [
            FxRate(currency="USD", date=date(2026, 1, 1), rate_to_base=17.0),
            FxRate(currency="USD", date=date(2026, 6, 1), rate_to_base=18.5),
        ],
        base="MXN",
    )


def test_rate_uses_latest_on_or_before_date() -> None:
    fx = _table()
    assert fx.rate("USD", date(2026, 3, 1)) == 17.0
    assert fx.rate("USD", date(2026, 6, 1)) == 18.5
    assert fx.rate("usd", date(2027, 1, 1)) == 18.5


def test_rate_before_history_uses_first_known() -> None:
    assert _table().rate("USD", date(2020, 1, 1)) == 17.0


def test_base_currency_is_one_and_missing_raises() -> None:
    fx = _table()
    assert fx.convert(100, "MXN", date(2026, 1, 1)) == 100
    with pytest.raises(MissingRateError):
        fx.rate("EUR", date(2026, 1, 1))


def _mock_client(rates: dict[str, float]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["base"] == "MXN"
        return httpx.Response(200, json={"base": "MXN", "rates": rates})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_fetch_latest_inverts_rates() -> None:
    result = fetch_latest({"USD", "MXN"}, _mock_client({"USD": 0.05}))
    assert result == {"USD": pytest.approx(20.0)}


def test_refresh_rates_persists(session: Session) -> None:
    assert refresh_rates(session, {"USD", "EUR"}, _mock_client({"USD": 0.05, "EUR": 0.04})) == 2
    stored = {r.currency: r for r in session.exec(select(FxRate)).all()}
    assert stored["EUR"].rate_to_base == pytest.approx(25.0)
    assert stored["EUR"].source == "frankfurter"


def test_refresh_rates_tolerates_network_errors(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert refresh_rates(session, {"USD"}, client) == 0
