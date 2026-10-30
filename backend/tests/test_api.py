from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_asset_crud_with_initial_valuation(client: TestClient) -> None:
    r = client.post(
        "/api/assets",
        json={"name": "Cetes", "type": "investment", "currency": "mxn", "initial_value": 50_000},
    )
    assert r.status_code == 201
    asset = r.json()
    assert asset["currency"] == "MXN"

    vals = client.get(f"/api/assets/{asset['id']}/valuations").json()
    assert [v["value"] for v in vals] == [50_000]

    # Misma fecha reemplaza; otra fecha agrega.
    client.post(
        f"/api/assets/{asset['id']}/valuations", json={"date": vals[0]["date"], "value": 51_000}
    )
    client.post(
        f"/api/assets/{asset['id']}/valuations", json={"date": "2020-01-01", "value": 10_000}
    )
    vals = client.get(f"/api/assets/{asset['id']}/valuations").json()
    assert [v["value"] for v in vals] == [10_000, 51_000]

    r = client.patch(f"/api/assets/{asset['id']}", json={"name": "CETES Directo"})
    assert r.json()["name"] == "CETES Directo"
    assert client.patch(f"/api/assets/{asset['id']}", json={"name": ""}).status_code == 422

    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    assert client.get(f"/api/assets/{asset['id']}").status_code == 404


def test_income_entries_and_summary(client: TestClient) -> None:
    source = client.post(
        "/api/income/sources",
        json={"name": "Freelance", "type": "freelance", "expected_amount": 20_000},
    ).json()
    entry = client.post(
        f"/api/income/sources/{source['id']}/entries",
        json={"date": "2026-01-15", "gross_amount": 25_000, "tax_withheld": 2_500},
    ).json()
    assert entry["net_amount"] == 22_500
    assert len(client.get("/api/income/entries", params={"source_id": source["id"]}).json()) == 1

    summary = client.get("/api/analytics/summary").json()
    assert summary["base_currency"] == "MXN"
    assert summary["monthly_income"] > 0


def test_expense_payments_reject_duplicates(client: TestClient) -> None:
    expense = client.post(
        "/api/expenses",
        json={
            "name": "Internet",
            "category": "utilities",
            "amount": 600,
            "due_day": 5,
            "start_date": "2026-01-01",
        },
    ).json()
    payment = {
        "expense_id": expense["id"],
        "due_date": "2026-02-05",
        "paid_date": "2026-02-04",
        "amount": 600,
    }
    assert client.post("/api/expenses/payments", json=payment).status_code == 201
    assert client.post("/api/expenses/payments", json=payment).status_code == 409
    assert len(client.get(f"/api/expenses/{expense['id']}/payments").json()) == 1


def test_manual_fx_rate_and_latest(client: TestClient) -> None:
    client.post("/api/assets", json={"name": "Wallet", "type": "crypto", "currency": "BTC"})
    client.post(
        "/api/fx/rates", json={"currency": "btc", "date": "2026-01-01", "rate_to_base": 2_000_000}
    )
    latest = {row["currency"]: row for row in client.get("/api/fx/latest").json()}
    assert latest["BTC"]["rate_to_base"] == 2_000_000
    assert latest["USD"]["rate_to_base"] is None


def test_export_import_roundtrip(client: TestClient) -> None:
    client.post("/api/assets", json={"name": "Ahorro", "type": "bank", "initial_value": 1_000})
    exported = client.get("/api/backup/export").json()
    client.post("/api/assets", json={"name": "Temporal", "type": "cash"})

    counts = client.post("/api/backup/import", json=exported).json()
    assert counts["asset"] == 1
    assert [a["name"] for a in client.get("/api/assets").json()] == ["Ahorro"]


def test_db_backup_download(client: TestClient) -> None:
    r = client.get("/api/backup/db")
    assert r.status_code == 200
    assert r.content.startswith(b"SQLite format 3")


def test_settings_normalize_values(client: TestClient) -> None:
    r = client.patch(
        "/api/settings",
        json={"currencies": ["usd", " eur", ""], "allowed_logins": ["Yo@Example.com"]},
    )
    data = r.json()
    assert data["currencies"] == ["EUR", "USD"]
    assert data["allowed_logins"] == ["yo@example.com"]


def test_projection_endpoint(client: TestClient) -> None:
    data = client.get(
        "/api/analytics/projection", params={"years": 3, "annual_return_pct": 5}
    ).json()
    assert len(data["points"]) == 4
    assert data["annual_return_pct"] == 5


def test_index_is_never_cached(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import importlib
    import os

    import mamoney.config as config
    import mamoney.main as main

    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<div id=root></div>")
    original = os.environ.get("MAMONEY_STATIC_DIR")
    os.environ["MAMONEY_STATIC_DIR"] = str(static)
    config.get_config.cache_clear()
    try:
        app = importlib.reload(main).create_app()
        with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 1)) as c:
            r = c.get("/inversiones")
            assert r.status_code == 200
            assert r.headers["cache-control"] == "no-cache"
    finally:
        if original is None:
            os.environ.pop("MAMONEY_STATIC_DIR", None)
        else:
            os.environ["MAMONEY_STATIC_DIR"] = original
        config.get_config.cache_clear()
        importlib.reload(main)


def test_export_covers_every_data_table() -> None:
    from sqlmodel import SQLModel

    from mamoney.routers.system import EXPORT_TABLES

    exported = {m.__tablename__ for m in EXPORT_TABLES}  # type: ignore[attr-defined]
    internal = {"setting", "alembic_version"}
    assert set(SQLModel.metadata.tables) - internal == exported
