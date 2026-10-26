import json
import subprocess
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from mamoney.services import tailscale

PORT = 8765  # puerto por defecto de la configuración de pruebas

STATUS = {
    "BackendState": "Running",
    "Self": {"DNSName": "mipc.tail1234.ts.net.", "HostName": "MiPC", "UserID": 42},
    "User": {"42": {"LoginName": "yo@example.com"}},
    "CertDomains": ["mipc.tail1234.ts.net"],
}

SERVE_ON = {
    "TCP": {"443": {"HTTPS": True}},
    "Web": {"mipc.tail1234.ts.net:443": {"Handlers": {"/": {"Proxy": f"http://127.0.0.1:{PORT}"}}}},
}


def _done(stdout: str = "", stderr: str = "", code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout, stderr=stderr)


class FakeCli:
    """Simula la CLI de Tailscale y registra los comandos ejecutados."""

    def __init__(self, status: dict | None = None, serve: dict | None = None) -> None:
        self.status = status if status is not None else STATUS
        self.serve = serve if serve is not None else {}
        self.calls: list[list[str]] = []
        self.on_serve: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None

    def __call__(self, args: list[str], timeout: float = 15) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        if args[:2] == ["status", "--json"]:
            return _done(json.dumps(self.status))
        if args[:3] == ["serve", "status", "--json"]:
            return _done(json.dumps(self.serve))
        if args[0] == "serve":
            if self.on_serve:
                return self.on_serve(args)
            self.serve = SERVE_ON if "off" not in args else {}
            return _done()
        raise AssertionError(f"comando inesperado: {args}")


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> FakeCli:
    fake = FakeCli()
    monkeypatch.setattr(tailscale, "find_cli", lambda: "tailscale")
    monkeypatch.setattr(tailscale, "_run", fake)
    return fake


def test_is_published_detects_our_port() -> None:
    assert tailscale.is_published(SERVE_ON, PORT)
    assert not tailscale.is_published(SERVE_ON, 9999)
    assert not tailscale.is_published({}, PORT)


def test_status_reads_url_login_and_publication(cli: FakeCli) -> None:
    cli.serve = SERVE_ON
    status = tailscale.get_status()
    assert status.running and status.https_enabled and status.published
    assert status.url == "https://mipc.tail1234.ts.net"
    assert status.login == "yo@example.com"


def test_status_when_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tailscale, "find_cli", lambda: None)
    assert tailscale.get_status().installed is False


def test_status_when_logged_out(cli: FakeCli) -> None:
    cli.status = {**STATUS, "BackendState": "NeedsLogin"}
    status = tailscale.get_status()
    assert not status.running and status.error


def test_publish_uses_serve_never_funnel(cli: FakeCli) -> None:
    status = tailscale.publish()
    assert status.published
    command = next(c for c in cli.calls if c[0] == "serve" and "status" not in c)
    assert command == ["serve", "--bg", "--yes", "--https=443", f"http://127.0.0.1:{PORT}"]
    assert not any("funnel" in part for call in cli.calls for part in call)


def test_publish_requires_https_certificates(cli: FakeCli) -> None:
    cli.status = {**STATUS, "CertDomains": None}
    with pytest.raises(tailscale.TailscaleError) as exc:
        tailscale.publish()
    assert exc.value.action_url == tailscale.HTTPS_HELP


def test_publish_reports_consent_link_when_cli_waits(cli: FakeCli) -> None:
    def waits(args: list[str]) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(
            args,
            20,
            output="Serve is not enabled on your tailnet.\nTo enable, visit:\n\n"
            "         https://login.tailscale.com/f/serve?node=abc123\n",
        )

    cli.on_serve = waits
    with pytest.raises(tailscale.TailscaleError) as exc:
        tailscale.publish()
    assert exc.value.action_url == "https://login.tailscale.com/f/serve?node=abc123"


def test_unpublish(cli: FakeCli) -> None:
    cli.serve = SERVE_ON
    assert tailscale.unpublish().published is False
    assert ["serve", "--https=443", "off"] in cli.calls


def test_api_status_and_publish_flow(client: TestClient, cli: FakeCli) -> None:
    assert client.get("/api/tailscale").json()["published"] is False
    assert client.post("/api/tailscale/publish").json()["published"] is True
    assert client.post("/api/tailscale/unpublish").json()["published"] is False


def test_api_error_includes_action_url(client: TestClient, cli: FakeCli) -> None:
    cli.status = {**STATUS, "CertDomains": None}
    r = client.post("/api/tailscale/publish")
    assert r.status_code == 409
    assert r.json()["detail"]["action_url"] == tailscale.HTTPS_HELP


def test_publish_only_from_local(tailnet_client: TestClient, cli: FakeCli) -> None:
    assert tailnet_client.get("/api/tailscale").status_code == 200
    assert tailnet_client.post("/api/tailscale/publish").status_code == 403
    assert tailnet_client.post("/api/tailscale/unpublish").status_code == 403
