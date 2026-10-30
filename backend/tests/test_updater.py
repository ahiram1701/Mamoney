import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from mamoney.services import updater

ZIP_NAME = "Mamoney-v0.3.0-windows-x64.zip"
BASE = "https://example.test"


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _release_json(version: str = "0.3.0", with_assets: bool = True) -> dict:
    assets = []
    if with_assets:
        assets = [
            {"name": ZIP_NAME, "browser_download_url": f"{BASE}/zip", "size": 10},
            {"name": f"{ZIP_NAME}.sha256", "browser_download_url": f"{BASE}/sha"},
        ]
    return {
        "tag_name": f"v{version}",
        "name": f"Mamoney v{version}",
        "body": "### Añadido\n- Algo nuevo",
        "published_at": "2026-11-01T00:00:00Z",
        "html_url": f"{BASE}/release",
        "assets": assets,
    }


def _client(zip_data: bytes, sha: str | None = None, release: dict | None = None) -> httpx.Client:
    digest = sha or hashlib.sha256(zip_data).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        if "api.github.com" in str(request.url):
            return httpx.Response(200, json=release or _release_json())
        if request.url.path == "/sha":
            return httpx.Response(200, text=f"{digest}  {ZIP_NAME}\n")
        if request.url.path == "/zip":
            return httpx.Response(200, content=zip_data)
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("latest", "current", "expected"),
    [
        ("0.2.0", "0.1.0", True),
        ("0.10.0", "0.9.9", True),
        ("1.0", "0.9.9", True),
        ("0.1.0", "0.1.0", False),
        ("0.1.0", "0.2.0", False),
        ("v0.2.0", "0.1.0", True),
    ],
)
def test_is_newer(latest: str, current: str, expected: bool) -> None:
    assert updater.is_newer(latest, current) is expected


def test_check_detects_new_release_and_assets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "current_version", lambda: "0.1.0")
    status = updater.check_for_updates(_client(b""))
    assert status.available
    assert status.latest and status.latest.zip_name == ZIP_NAME
    assert status.latest.sha256_url == f"{BASE}/sha"
    # En pruebas no corre como Mamoney.exe: puede avisar, pero no instalar solo.
    assert status.can_install is False


def test_check_without_newer_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "current_version", lambda: "0.3.0")
    assert updater.check_for_updates(_client(b"")).available is False


def test_check_tolerates_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    status = updater.check_for_updates(httpx.Client(transport=httpx.MockTransport(handler)))
    assert status.error and "GitHub" in status.error
    assert status.available is False or status.latest is not None


def test_release_without_checksum_is_not_installable(monkeypatch: pytest.MonkeyPatch) -> None:
    release = _release_json(with_assets=False)
    info = updater.fetch_latest_release(_client(b"", release=release))
    assert info and info.zip_url is None


def test_download_verifies_checksum(tmp_path: Path) -> None:
    data = _zip_bytes({"Mamoney/Mamoney.exe": b"exe"})
    info = updater.fetch_latest_release(_client(data))
    assert info
    path = updater.download_verified(info, tmp_path, _client(data))
    assert path.read_bytes() == data


def test_download_rejects_tampered_package(tmp_path: Path) -> None:
    data = _zip_bytes({"Mamoney/Mamoney.exe": b"exe"})
    client = _client(data, sha="0" * 64)
    info = updater.fetch_latest_release(client)
    assert info
    with pytest.raises(updater.UpdateError, match="checksum"):
        updater.download_verified(info, tmp_path, client)
    assert not list(tmp_path.iterdir())  # no queda basura a medio descargar


def test_parse_sha256_file() -> None:
    digest = "a" * 64
    assert updater.parse_sha256_file(f"{digest.upper()}  archivo.zip") == digest
    with pytest.raises(updater.UpdateError):
        updater.parse_sha256_file("nada")


def test_extract_finds_app_folder(tmp_path: Path) -> None:
    zip_path = tmp_path / "pkg.zip"
    zip_path.write_bytes(_zip_bytes({"Mamoney/Mamoney.exe": b"exe", "Mamoney/_internal/x": b"1"}))
    app = updater.extract_release(zip_path, tmp_path / "staging")
    assert (app / "Mamoney.exe").read_bytes() == b"exe"


def test_extract_rejects_path_traversal(tmp_path: Path) -> None:
    zip_path = tmp_path / "evil.zip"
    zip_path.write_bytes(_zip_bytes({"../fuera.txt": b"x", "Mamoney/Mamoney.exe": b"exe"}))
    with pytest.raises(updater.UpdateError, match="insegura"):
        updater.extract_release(zip_path, tmp_path / "staging")
    assert not (tmp_path / "fuera.txt").exists()


def test_extract_requires_executable(tmp_path: Path) -> None:
    zip_path = tmp_path / "pkg.zip"
    zip_path.write_bytes(_zip_bytes({"otra-cosa.txt": b"x"}))
    with pytest.raises(updater.UpdateError, match=r"Mamoney\.exe"):
        updater.extract_release(zip_path, tmp_path / "staging")


def test_install_flow_launches_updater(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install = tmp_path / "apps" / "Mamoney"
    install.mkdir(parents=True)
    monkeypatch.setattr(updater, "can_self_install", lambda: True)
    monkeypatch.setattr(updater, "install_dir", lambda: install)
    monkeypatch.setattr(updater, "current_version", lambda: "0.1.0")
    monkeypatch.setattr(updater, "_shutdown_handler", None)

    data = _zip_bytes({"Mamoney/Mamoney.exe": b"nuevo"})
    launched: list[list[str]] = []
    version = updater.install_update(
        client=_client(data), launch=lambda cmd, cwd: launched.append(cmd)
    )

    assert version == "0.3.0"
    cmd = launched[0]
    assert cmd[0] == "powershell.exe"
    assert cmd[cmd.index("-Target") + 1] == str(install)
    source = Path(cmd[cmd.index("-Source") + 1])
    assert (source / "Mamoney.exe").read_bytes() == b"nuevo"
    script = Path(cmd[cmd.index("-File") + 1]).read_text(encoding="utf-8-sig")
    assert "Restaurando la versión anterior" in script
    backups = list((updater.get_config().backup_dir).glob("antes-de-v0.3.0-*.db"))
    assert backups, "debe respaldar la base antes de actualizar"


def test_install_refused_outside_executable() -> None:
    with pytest.raises(updater.UpdateError, match=r"Mamoney\.exe"):
        updater.install_update()


def test_updates_api(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updater, "current_version", lambda: "0.1.0")
    real_check = updater.check_for_updates
    monkeypatch.setattr(updater, "check_for_updates", lambda: real_check(_client(b"")))
    data = client.get("/api/updates", params={"refresh": True}).json()
    assert data["available"] is True
    assert data["latest"]["version"] == "0.3.0"
    assert client.post("/api/updates/install").status_code == 409


def test_install_api_is_local_only(tailnet_client: TestClient) -> None:
    assert tailnet_client.post("/api/updates/install").status_code == 403


def test_status_without_auto_check_does_not_call_github(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(updater, "_status", None)

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("no debe consultar GitHub")

    monkeypatch.setattr(updater, "check_for_updates", boom)
    data = client.get("/api/updates").json()
    assert data["available"] is False
    assert data["latest"] is None


def test_updater_command_passes_port_and_dedicated_webview_dir(tmp_path: Path) -> None:
    cmd = updater.updater_command(
        tmp_path / "s.ps1", tmp_path / "src", tmp_path / "dst", tmp_path / "l"
    )
    cfg = updater.get_config()
    assert cmd[cmd.index("-Port") + 1] == str(cfg.port)
    assert cmd[cmd.index("-WebviewDir") + 1] == str(cfg.webview_dir)
    assert cfg.webview_dir.parent == cfg.data_dir  # no la carpeta compartida de pywebview


def test_updater_script_waits_for_webview_and_checks_health() -> None:
    script = updater.UPDATER_SCRIPT
    assert "Wait-Webview" in script and "/api/health" in script
    assert script.count("Start-Mamoney") >= 3  # definición + éxito + restauración
