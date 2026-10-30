import datetime as dt

from fastapi.testclient import TestClient
from sqlmodel import Session

from mamoney.services.alerts import build_alerts, take_new_alerts

TODAY = dt.date.today()


def _setup(client: TestClient) -> None:
    client.post(
        "/api/expenses",
        json={
            "name": "Internet",
            "category": "utilities",
            "amount": 600,
            "due_day": TODAY.day,
            "start_date": (TODAY - dt.timedelta(days=400)).isoformat(),
        },
    )
    client.post(
        "/api/spending",
        json={
            "date": TODAY.isoformat(),
            "amount": 1200,
            "category": "restaurants",
            "description": "x",
        },
    )
    client.put("/api/budget", json={"limits": {"restaurants": 1000}})


def test_alerts_cover_payments_and_budget(client: TestClient, session: Session) -> None:
    _setup(client)
    alerts = client.get("/api/alerts").json()
    kinds = {a["kind"] for a in alerts}
    assert {"payment", "budget"} <= kinds
    budget = next(a for a in alerts if a["kind"] == "budget")
    assert budget["severity"] == "critical" and "excedido" in budget["title"]
    payment = next(a for a in alerts if a["kind"] == "payment")
    assert "Internet" in payment["title"]


def test_paid_payment_has_no_alert(client: TestClient, session: Session) -> None:
    _setup(client)
    expense = client.get("/api/expenses").json()[0]
    client.post(
        "/api/expenses/payments",
        json={
            "expense_id": expense["id"],
            "due_date": TODAY.isoformat(),
            "paid_date": TODAY.isoformat(),
            "amount": 600,
        },
    )
    assert not [
        a for a in build_alerts(session) if a["kind"] == "payment" and TODAY.isoformat() in a["key"]
    ]


def test_each_alert_is_notified_once_and_can_be_disabled(
    client: TestClient, session: Session
) -> None:
    _setup(client)
    first = take_new_alerts(session)
    assert first
    assert take_new_alerts(session) == []  # ya notificadas
    client.patch("/api/settings", json={"alerts_enabled": False})
    assert take_new_alerts(session) == []
