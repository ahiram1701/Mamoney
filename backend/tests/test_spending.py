import datetime as dt

import pytest
from fastapi.testclient import TestClient

from mamoney.models import Spending, SpendingCategory
from mamoney.services import analytics as an
from mamoney.services.fx import FxTable

TODAY = dt.date(2026, 6, 15)


def _snap(spendings: list[Spending]) -> an.Snapshot:
    snap = an.Snapshot([], {}, [], [], [], [], FxTable([], base="MXN"), TODAY)
    snap.spendings = spendings
    return snap


def _s(day: dt.date, amount: float, cat: SpendingCategory = SpendingCategory.groceries) -> Spending:
    return Spending(date=day, amount=amount, category=cat, description="x")


def test_monthly_average_uses_complete_months() -> None:
    snap = _snap(
        [
            _s(dt.date(2026, 3, 5), 3000),
            _s(dt.date(2026, 4, 5), 4000),
            _s(dt.date(2026, 5, 5), 5000),
            _s(dt.date(2026, 6, 1), 99999),  # mes en curso: no cuenta
        ]
    )
    assert an.monthly_variable_spending(snap) == pytest.approx(4000)


def test_monthly_average_projects_first_partial_month() -> None:
    snap = _snap([_s(dt.date(2026, 6, 2), 1500)])
    assert an.monthly_variable_spending(snap) == pytest.approx(1500 / 15 * 30)


def test_budget_status_and_projection() -> None:
    snap = _snap(
        [
            _s(TODAY, 4000),
            _s(TODAY, 900, SpendingCategory.restaurants),
            _s(TODAY, 300, SpendingCategory.transport),
        ]
    )
    report = an.budget_report(
        snap, {"groceries": 6000, "restaurants": 800, "transport": 2000}, 2026, 6
    )
    by_cat = {r["category"]: r for r in report["categories"]}
    assert by_cat["restaurants"]["status"] == "over"
    assert by_cat["groceries"]["status"] == "warning"  # proyecta 8,000 > 6,000
    assert by_cat["groceries"]["projected"] == pytest.approx(8000)
    assert by_cat["transport"]["status"] == "ok"
    assert report["spent"] == 5200 and report["limit"] == 8800


def test_summary_free_cash_flow_includes_variable() -> None:
    snap = _snap([_s(dt.date(2026, 5, 5), 2500)])
    assert an.summary(snap)["monthly_variable_spending"] == 2500
    assert an.summary(snap)["free_cash_flow"] == -2500


def test_spending_and_budget_api(client: TestClient) -> None:
    today = dt.date.today()
    month = f"{today.year:04d}-{today.month:02d}"
    r = client.post(
        "/api/spending",
        json={
            "date": today.isoformat(),
            "amount": 850,
            "category": "groceries",
            "description": "Súper",
        },
    )
    assert r.status_code == 201
    spending_id = r.json()["id"]
    assert len(client.get("/api/spending", params={"month": month}).json()) == 1
    client.patch(f"/api/spending/{spending_id}", json={"category": "restaurants"})

    assert client.put(
        "/api/budget", json={"limits": {"restaurants": 1000, "groceries": None}}
    ).json() == {"restaurants": 1000}
    report = client.get("/api/analytics/budget", params={"month": month}).json()
    assert report["categories"][0]["category"] == "restaurants"
    assert report["categories"][0]["spent"] == 850
    assert client.get("/api/analytics/budget", params={"month": "2026-13"}).status_code == 422
    assert client.delete(f"/api/spending/{spending_id}").status_code == 204
