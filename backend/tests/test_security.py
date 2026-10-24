from fastapi.testclient import TestClient

from mamoney.main import app
from mamoney.security import hash_pin, make_session_token, valid_session_token, verify_pin


def test_local_window_is_allowed(client: TestClient) -> None:
    status = client.get("/api/auth/status").json()
    assert status["authorized"] and status["is_local"]


def test_tailnet_identity_is_allowed(tailnet_client: TestClient) -> None:
    status = tailnet_client.get("/api/auth/status").json()
    assert status["authorized"]
    assert status["identity"] == "yo@example.com"
    assert tailnet_client.get("/api/assets").status_code == 200


def test_request_without_identity_is_rejected() -> None:
    # Tailscale Funnel (público) llega desde loopback pero sin identidad.
    with TestClient(app, base_url="https://pc.tailnet.ts.net", client=("127.0.0.1", 1)) as c:
        assert c.get("/api/assets").status_code == 403
        assert c.get("/").status_code == 403


def test_non_loopback_client_is_rejected() -> None:
    with TestClient(
        app,
        base_url="http://127.0.0.1:8765",
        client=("100.64.0.9", 1),
        headers={"Tailscale-User-Login": "yo@example.com"},
    ) as c:
        assert c.get("/api/assets").status_code == 403


def test_allowed_logins_restrict_identity(client: TestClient, tailnet_client: TestClient) -> None:
    client.patch("/api/settings", json={"allowed_logins": ["otra@example.com"]})
    assert tailnet_client.get("/api/assets").status_code == 403
    client.patch("/api/settings", json={"allowed_logins": ["yo@example.com"]})
    assert tailnet_client.get("/api/assets").status_code == 200


def test_pin_flow(client: TestClient, tailnet_client: TestClient) -> None:
    assert client.put("/api/settings/pin", json={"pin": "12a"}).status_code == 422
    client.put("/api/settings/pin", json={"pin": "2468"})

    assert client.get("/api/assets").status_code == 200  # local no pide PIN
    r = tailnet_client.get("/api/assets")
    assert r.status_code == 401 and r.json()["detail"] == "pin_required"

    assert tailnet_client.post("/api/auth/pin", json={"pin": "0000"}).status_code == 401
    assert tailnet_client.post("/api/auth/pin", json={"pin": "2468"}).status_code == 200
    assert tailnet_client.get("/api/assets").status_code == 200

    client.put("/api/settings/pin", json={"pin": None})
    assert client.get("/api/settings").json()["pin_enabled"] is False


def test_pin_hash_and_tokens() -> None:
    stored = hash_pin("1234")
    assert verify_pin("1234", stored) and not verify_pin("4321", stored)
    token = make_session_token("s3cret")
    assert valid_session_token("s3cret", token)
    assert not valid_session_token("otro", token)
    assert not valid_session_token("s3cret", make_session_token("s3cret", ttl=-1))
    assert not valid_session_token("s3cret", "basura")
