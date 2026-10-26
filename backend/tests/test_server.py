"""Pruebas contra un Uvicorn real: TestClient no pasa por sus middlewares de proxy."""

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from mamoney.main import server_config


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    port = _free_port()
    server = uvicorn.Server(server_config(port=port, log_config=None))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started:
        if time.time() > deadline:
            raise RuntimeError("Uvicorn no arrancó")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


# Lo que envía `tailscale serve` al reenviar una petición de un teléfono de la tailnet.
TAILSCALE_HEADERS = {
    "Host": "mipc.tail1234.ts.net",
    "X-Forwarded-For": "100.125.93.102",
    "X-Forwarded-Proto": "https",
    "Tailscale-User-Login": "yo@example.com",
}


def test_tailnet_request_through_proxy_is_accepted(base_url: str) -> None:
    # Regresión: Uvicorn confiaba en X-Forwarded-For y el cliente dejaba de ser 127.0.0.1.
    r = httpx.get(f"{base_url}/api/auth/status", headers=TAILSCALE_HEADERS)
    data = r.json()
    assert data["authorized"] is True, data
    assert data["identity"] == "yo@example.com"
    assert httpx.get(f"{base_url}/api/assets", headers=TAILSCALE_HEADERS).status_code == 200


def test_proxied_request_without_identity_is_rejected(base_url: str) -> None:
    headers = {k: v for k, v in TAILSCALE_HEADERS.items() if k != "Tailscale-User-Login"}
    assert httpx.get(f"{base_url}/api/assets", headers=headers).status_code == 403


def test_local_window_still_works(base_url: str) -> None:
    data = httpx.get(f"{base_url}/api/auth/status").json()
    assert data["authorized"] and data["is_local"]
