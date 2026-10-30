"""Publicación del dashboard en la tailnet con `tailscale serve`.

Mamoney sigue escuchando solo en 127.0.0.1; `tailscale serve` lo expone con HTTPS únicamente
a los dispositivos de la tailnet. Nunca se usa `tailscale funnel` (internet público).
"""

import json
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mamoney.config import get_config

WINDOWS_PATHS = [Path(r"C:\Program Files\Tailscale\tailscale.exe")]
MAC_PATHS = [Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")]
LOGIN_URL = re.compile(r"https://login\.tailscale\.com/\S+")
HTTPS_HELP = "https://login.tailscale.com/admin/dns"


class TailscaleError(RuntimeError):
    def __init__(self, message: str, action_url: str | None = None) -> None:
        super().__init__(message)
        self.action_url = action_url


@dataclass
class TailscaleStatus:
    installed: bool
    running: bool = False
    published: bool = False
    https_enabled: bool = False
    url: str | None = None
    hostname: str | None = None
    login: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def find_cli() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    candidates = WINDOWS_PATHS if sys.platform == "win32" else MAC_PATHS
    return next((str(p) for p in candidates if p.exists()), None)


def _run(args: list[str], timeout: float = 15) -> subprocess.CompletedProcess[str]:
    cli = find_cli()
    if cli is None:
        raise TailscaleError("Tailscale no está instalado en este equipo")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # sin consola parpadeando
    return subprocess.run(
        [cli, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=flags,
        check=False,
    )


def _local_targets(port: int) -> set[str]:
    return {f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"127.0.0.1:{port}"}


def is_published(serve_config: dict[str, Any], port: int) -> bool:
    """¿Algún handler de `tailscale serve` apunta a nuestro puerto local?"""
    targets = _local_targets(port)
    for site in (serve_config.get("Web") or {}).values():
        for handler in (site.get("Handlers") or {}).values():
            if str(handler.get("Proxy", "")).rstrip("/") in targets:
                return True
    return False


def get_status() -> TailscaleStatus:
    if find_cli() is None:
        return TailscaleStatus(installed=False)
    try:
        raw = _run(["status", "--json"])
        if raw.returncode != 0 or not raw.stdout.strip().startswith("{"):
            message = (raw.stderr or raw.stdout).strip() or "Tailscale no está conectado"
            return TailscaleStatus(installed=True, error=message)
        data = json.loads(raw.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        return TailscaleStatus(installed=True, error=f"No se pudo leer el estado: {exc}")

    me = data.get("Self") or {}
    dns = str(me.get("DNSName") or "").rstrip(".")
    users = data.get("User") or {}
    login = (users.get(str(me.get("UserID"))) or {}).get("LoginName")
    status = TailscaleStatus(
        installed=True,
        running=data.get("BackendState") == "Running",
        https_enabled=bool(data.get("CertDomains")),
        url=f"https://{dns}" if dns else None,
        hostname=me.get("HostName"),
        login=login,
    )
    if not status.running:
        status.error = "Tailscale no está conectado. Ábrelo e inicia sesión."
        return status
    try:
        serve = _run(["serve", "status", "--json"])
        config = json.loads(serve.stdout) if serve.stdout.strip().startswith("{") else {}
        status.published = is_published(config, get_config().port)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return status


def _raise_from_output(output: str) -> None:
    url_match = LOGIN_URL.search(output)
    lowered = output.lower()
    if "https" in lowered and ("cert" in lowered or "not enabled" in lowered) and not url_match:
        raise TailscaleError(
            "Activa los certificados HTTPS en la consola de Tailscale y vuelve a intentarlo.",
            HTTPS_HELP,
        )
    if url_match:
        raise TailscaleError(
            "Tailscale necesita que autorices Serve en tu red. Abre el enlace, acéptalo y "
            "vuelve a intentarlo.",
            url_match.group(0).rstrip(".,)"),
        )
    raise TailscaleError(output.strip() or "Tailscale rechazó la operación")


def publish() -> TailscaleStatus:
    status = get_status()
    if not status.installed:
        raise TailscaleError(
            "Tailscale no está instalado en este equipo", "https://tailscale.com/download"
        )
    if not status.running:
        raise TailscaleError(status.error or "Tailscale no está conectado")
    if not status.https_enabled:
        raise TailscaleError(
            "Activa los certificados HTTPS en la consola de Tailscale y vuelve a intentarlo.",
            HTTPS_HELP,
        )
    target = f"http://127.0.0.1:{get_config().port}"
    try:
        result = _run(["serve", "--bg", "--yes", "--https=443", target], timeout=20)
    except subprocess.TimeoutExpired as exc:
        # Si Serve no está habilitado en la tailnet, la CLI imprime un enlace y espera.
        partial = exc.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        _raise_from_output(partial + str(exc.stderr or ""))
        raise  # pragma: no cover
    if result.returncode != 0:
        _raise_from_output(result.stdout + "\n" + result.stderr)
    return get_status()


def unpublish() -> TailscaleStatus:
    result = _run(["serve", "--https=443", "off"])
    if result.returncode != 0 and "not found" not in (result.stderr + result.stdout).lower():
        raise TailscaleError((result.stderr or result.stdout).strip() or "No se pudo desactivar")
    return get_status()


_devices: dict[str, str] = {}
_devices_at = 0.0
_devices_lock = threading.Lock()
DEVICES_TTL = 300


def device_name(ip: str | None) -> str | None:
    """Nombre del dispositivo de la tailnet con esa IP (caché de 5 min; None si no se sabe)."""
    global _devices_at
    if not ip:
        return None
    with _devices_lock:
        if time.monotonic() - _devices_at > DEVICES_TTL:
            _devices_at = time.monotonic()
            try:
                data = json.loads(_run(["status", "--json"], timeout=5).stdout or "{}")
                peers = [data.get("Self") or {}, *(data.get("Peer") or {}).values()]
                _devices.clear()
                for peer in peers:
                    for addr in peer.get("TailscaleIPs") or []:
                        _devices[addr] = str(peer.get("HostName") or peer.get("DNSName") or addr)
            except (TailscaleError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
                pass
        return _devices.get(ip)
