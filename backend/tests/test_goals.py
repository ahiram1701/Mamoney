import datetime as dt

import pytest
from fastapi.testclient import TestClient

from mamoney.models import Asset, AssetType, AssetValuation, Goal
from mamoney.services import analytics as an
from mamoney.services.fx import FxTable

TODAY = dt.date(2026, 7, 1)


def _snap(values: list[tuple[dt.date, float]]) -> an.Snapshot:
    asset = Asset(id=1, name="Fondo", type=AssetType.bank)
    vals = [AssetValuation(id=i, asset_id=1, date=d, value=v) for i, (d, v) in enumerate(values, 1)]
    return an.Snapshot([asset], {1: vals}, [], [], [], [], FxTable([], base="MXN"), TODAY)


def test_goal_linked_to_asset_uses_its_growth() -> None:
    snap = _snap([(dt.date(2026, 1, 1), 40000), (dt.date(2026, 7, 1), 70000)])
    goal = Goal(
        id=1, name="Emergencias", target_amount=100000, target_date=dt.date(2027, 1, 1), asset_id=1
    )
    row = an.goal_progress(snap, goal, monthly_savings=0)
    assert row["current"] == 70000 and row["pct"] == 70
    assert row["monthly_pace"] == pytest.approx(30000 / (181 / 30.4375), rel=1e-3)
    assert row["monthly_needed"] == pytest.approx(30000 / (184 / 30.4375), rel=1e-3)
    assert row["status"] == "on_track"


def test_manual_goal_uses_free_cash_flow_and_detects_behind() -> None:
    snap = _snap([])
    goal = Goal(
        id=2,
        name="Viaje",
        target_amount=60000,
        target_date=dt.date(2026, 10, 1),
        manual_amount=10000,
    )
    row = an.goal_progress(snap, goal, monthly_savings=5000)
    assert row["remaining"] == 50000
    assert row["status"] == "behind"  # a 5,000/mes tarda 10 meses y quedan 3


def test_done_and_overdue() -> None:
    snap = _snap([])
    done = Goal(id=3, name="Hecha", target_amount=1000, manual_amount=1500)
    assert an.goal_progress(snap, done, 0)["status"] == "done"
    late = Goal(id=4, name="Tarde", target_amount=1000, target_date=dt.date(2026, 6, 1))
    assert an.goal_progress(snap, late, 100)["status"] == "overdue"


def test_goals_api(client: TestClient) -> None:
    asset = client.post(
        "/api/assets", json={"name": "Ahorro", "type": "bank", "initial_value": 25000}
    ).json()
    goal = client.post(
        "/api/goals", json={"name": "Enganche", "target_amount": 100000, "asset_id": asset["id"]}
    ).json()
    rows = client.get("/api/goals").json()
    assert rows[0]["current"] == 25000 and rows[0]["asset_name"] == "Ahorro"
    client.patch(f"/api/goals/{goal['id']}", json={"archived": True})
    assert client.get("/api/goals").json() == []
    assert len(client.get("/api/goals", params={"include_archived": True}).json()) == 1
    assert client.delete(f"/api/goals/{goal['id']}").status_code == 204
