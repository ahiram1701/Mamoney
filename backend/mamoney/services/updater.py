"""Actualizaciones desde GitHub Releases.

Flujo de instalación (solo en el ejecutable de Windows):

1. Consulta el último release y compara su versión con la instalada.
2. Descarga el `.zip` y su `.sha256`, y verifica el hash antes de usar nada.
3. Respalda la base de datos y extrae el `.zip` en una carpeta temporal, sin permitir
   rutas fuera de ella.
4. Lanza un script de PowerShell independiente que espera a que Mamoney cierre, mueve la
   versión actual a `<carpeta>.old`, copia la nueva y la abre. Si algo falla, restaura la
   anterior. Windows no permite sobrescribir un `.exe` en ejecución, por eso el cambio lo
   hace otro proceso.
"""

import hashlib
import hmac
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from mamoney import __version__
from mamoney.config import get_config

log = logging.getLogger(__name__)

API_URL = "https://api.github.com/repos/{repo}/releases/latest"
ZIP_PATTERN = re.compile(r"^Mamoney-v[\w.\-]+-windows-x64\.zip$")
EXE_NAME = "Mamoney.exe"
APP_FOLDER = "Mamoney"


class UpdateError(RuntimeError):
    pass


@dataclass
class ReleaseInfo:
    version: str
    tag: str
    name: str
    notes: str
    published_at: str | None
    html_url: str
    zip_url: str | None = None
    zip_name: str | None = None
    zip_size: int | None = None
    sha256_url: str | None = None


@dataclass
class UpdateStatus:
    current: str
    latest: ReleaseInfo | None = None
    available: bool = False
    checked_at: str | None = None
    error: str | None = None
    can_install: bool = False
    installing: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("extra")
        return data


def current_version() -> str:
    return get_config().version_override or __version__


def parse_version(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value.split("-", 1)[0].split("+", 1)[0])
    return tuple(int(p) for p in parts[:3]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    def pad(v: tuple[int, ...]) -> tuple[int, ...]:
        return v + (0,) * (3 - len(v))

    return pad(parse_version(latest)) > pad(parse_version(current))


def can_self_install() -> bool:
    """Solo el ejecutable empaquetado de Windows puede reemplazarse a sí mismo."""
    return bool(getattr(sys, "frozen", False)) and sys.platform == "win32"


def install_dir() -> Path:
    return Path(sys.executable).resolve().parent


def _client(client: httpx.Client | None, timeout: float) -> tuple[httpx.Client, bool]:
    if client is not None:
        return client, False
    headers = {"User-Agent": f"Mamoney/{current_version()}"}
    return httpx.Client(timeout=timeout, headers=headers, follow_redirects=True), True


def fetch_latest_release(client: httpx.Client | None = None) -> ReleaseInfo | None:
    http, own = _client(client, 10)
    try:
        resp = http.get(
            API_URL.format(repo=get_config().update_repo),
            headers={"Accept": "application/vnd.github+json"},
        )
        if resp.status_code == 404:
            return None  # el repositorio aún no tiene releases
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own:
            http.close()

    tag = str(data.get("tag_name", ""))
    info = ReleaseInfo(
        version=tag.lstrip("v"),
        tag=tag,
        name=str(data.get("name") or tag),
        notes=str(data.get("body") or ""),
        published_at=data.get("published_at"),
        html_url=str(data.get("html_url", "")),
    )
    assets = {a.get("name"): a for a in data.get("assets", [])}
    for name, asset in assets.items():
        if name and ZIP_PATTERN.match(name) and f"{name}.sha256" in assets:
            info.zip_name = name
            info.zip_url = asset.get("browser_download_url")
            info.zip_size = asset.get("size")
            info.sha256_url = assets[f"{name}.sha256"].get("browser_download_url")
            break
    return info


_lock = threading.Lock()
_install_lock = threading.Lock()
_status: UpdateStatus | None = None


def last_status() -> UpdateStatus | None:
    with _lock:
        return _status


def check_for_updates(client: httpx.Client | None = None) -> UpdateStatus:
    global _status
    current = current_version()
    now = datetime.now(UTC).isoformat()
    try:
        latest = fetch_latest_release(client)
        error = None
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("No se pudo consultar la última versión: %s", exc)
        previous = last_status()
        latest = previous.latest if previous else None
        error = f"No se pudo consultar GitHub: {exc}"

    available = bool(latest and is_newer(latest.version, current))
    status = UpdateStatus(
        current=current,
        latest=latest,
        available=available,
        checked_at=now,
        error=error,
        can_install=bool(
            available and can_self_install() and latest and latest.zip_url and latest.sha256_url
        ),
        installing=_install_lock.locked(),
    )
    with _lock:
        _status = status
    return status


def parse_sha256_file(text: str) -> str:
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if not match:
        raise UpdateError("El archivo .sha256 no contiene un hash válido")
    return match.group(1).lower()


def download_verified(
    info: ReleaseInfo,
    dest_dir: Path,
    client: httpx.Client | None = None,
    progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    """Descarga el `.zip` y lo devuelve solo si su SHA-256 coincide con el publicado."""
    if not info.zip_url or not info.sha256_url or not info.zip_name:
        raise UpdateError("El release no incluye el paquete de Windows con su checksum")
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / info.zip_name
    partial = target.with_suffix(".part")

    http, own = _client(client, 60)
    try:
        sha_resp = http.get(info.sha256_url)
        sha_resp.raise_for_status()
        expected = parse_sha256_file(sha_resp.text)

        digest = hashlib.sha256()
        done = 0
        with http.stream("GET", info.zip_url) as resp, partial.open("wb") as fh:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0)) or info.zip_size
            for chunk in resp.iter_bytes(1024 * 256):
                fh.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except httpx.HTTPError as exc:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"Falló la descarga: {exc}") from exc
    finally:
        if own:
            http.close()

    actual = digest.hexdigest()
    if not hmac.compare_digest(actual, expected):
        partial.unlink(missing_ok=True)
        raise UpdateError("El checksum no coincide: la descarga está dañada o fue alterada")
    partial.replace(target)
    return target


def extract_release(zip_path: Path, staging: Path) -> Path:
    """Extrae el paquete y devuelve la carpeta que contiene `Mamoney.exe`."""
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    root = staging.resolve()
    try:
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                destination = (root / member).resolve()
                if destination != root and root not in destination.parents:
                    raise UpdateError(f"Ruta insegura en el paquete: {member}")
            zf.extractall(root)
    except zipfile.BadZipFile as exc:
        raise UpdateError("El paquete descargado no es un .zip válido") from exc

    for candidate in (root / APP_FOLDER, root):
        if (candidate / EXE_NAME).is_file():
            return candidate
    raise UpdateError(f"El paquete no contiene {EXE_NAME}")


UPDATER_SCRIPT = r"""
param(
    [int]$AppPid,
    [string]$Source,
    [string]$Target,
    [string]$ExeName,
    [string]$Log
)
$ErrorActionPreference = "Stop"
function Write-Log([string]$Message) {
    Add-Content -LiteralPath $Log -Value ("{0:u}  {1}" -f (Get-Date), $Message) -Encoding utf8
}
function Retry([scriptblock]$Action) {
    for ($i = 1; $i -le 10; $i++) {
        try { & $Action; return } catch { if ($i -eq 10) { throw }; Start-Sleep -Seconds 1 }
    }
}

Write-Log "Esperando a que Mamoney (PID $AppPid) termine"
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Process -Id $AppPid -ErrorAction SilentlyContinue) -and ((Get-Date) -lt $deadline)) {
    Start-Sleep -Milliseconds 300
}
if (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {
    Write-Log "Mamoney no se cerró a tiempo; se cancela la actualización"
    exit 1
}

$backup = "$Target.old"
try {
    if (Test-Path -LiteralPath $backup) {
        Retry { Remove-Item -LiteralPath $backup -Recurse -Force }
    }
    Retry { Move-Item -LiteralPath $Target -Destination $backup }
    Copy-Item -LiteralPath $Source -Destination $Target -Recurse
    Write-Log "Archivos reemplazados en $Target"
    Start-Process -FilePath (Join-Path $Target $ExeName) -WorkingDirectory $Target
    Remove-Item -LiteralPath $backup -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $Source -Recurse -Force -ErrorAction SilentlyContinue
    Write-Log "Actualización completada"
} catch {
    Write-Log "Error: $_. Restaurando la versión anterior"
    if (Test-Path -LiteralPath $backup) {
        if (Test-Path -LiteralPath $Target) {
            Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction SilentlyContinue
        }
        Move-Item -LiteralPath $backup -Destination $Target
    }
    Start-Process -FilePath (Join-Path $Target $ExeName) -WorkingDirectory $Target
    exit 1
}
"""


def write_updater_script(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    script = directory / "apply-update.ps1"
    # BOM para que Windows PowerShell 5.1 lea correctamente los acentos.
    script.write_text(UPDATER_SCRIPT.lstrip(), encoding="utf-8-sig")
    return script


def updater_command(script: Path, source: Path, target: Path, log_file: Path) -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-AppPid",
        str(os.getpid()),
        "-Source",
        str(source),
        "-Target",
        str(target),
        "-ExeName",
        EXE_NAME,
        "-Log",
        str(log_file),
    ]


def _check_writable(folder: Path) -> None:
    probe = folder / ".mamoney-write-test"
    try:
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        raise UpdateError(
            f"Sin permiso de escritura en {folder}. Mueve Mamoney a una carpeta de tu usuario."
        ) from exc


_shutdown_handler: Callable[[], None] | None = None


def set_shutdown_handler(handler: Callable[[], None]) -> None:
    """La app de escritorio registra cómo cerrarse para que el script pueda reemplazarla."""
    global _shutdown_handler
    _shutdown_handler = handler


def install_update(
    status: UpdateStatus | None = None,
    client: httpx.Client | None = None,
    launch: Callable[[list[str], Path], None] | None = None,
) -> str:
    """Descarga, verifica y aplica la última versión. Devuelve la versión instalada."""
    if not can_self_install():
        raise UpdateError("La instalación automática solo está disponible en Mamoney.exe")
    if not _install_lock.acquire(blocking=False):
        raise UpdateError("Ya hay una actualización en curso")
    try:
        status = status or check_for_updates(client)
        info = status.latest
        if not status.available or info is None:
            raise UpdateError("Ya tienes la versión más reciente")

        cfg = get_config()
        target = install_dir()
        _check_writable(target.parent)

        from mamoney.routers.system import backup_database

        cfg.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_database(cfg.backup_dir / f"antes-de-v{info.version}-{stamp}.db")

        work = cfg.updates_dir
        zip_path = download_verified(info, work, client)
        app_dir = extract_release(zip_path, work / f"v{info.version}")
        script = write_updater_script(work)
        command = updater_command(script, app_dir, target, work / "update.log")
        (launch or _launch_detached)(command, work)
        zip_path.unlink(missing_ok=True)

        log.info("Actualización a v%s preparada; cerrando Mamoney", info.version)
        if _shutdown_handler:
            threading.Timer(1.0, _shutdown_handler).start()
        return info.version
    except Exception:
        _install_lock.release()
        raise


def _launch_detached(command: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    # Evita que el nuevo Mamoney.exe herede el entorno interno de PyInstaller.
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    # CREATE_NO_WINDOW da a PowerShell una consola invisible; con DETACHED_PROCESS (sin
    # consola) PowerShell 5.1 termina antes de ejecutar el script.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "CREATE_NEW_PROCESS_GROUP", 0
    )
    # Si Mamoney corre dentro de un Job Object (algunos lanzadores y terminales lo hacen),
    # Windows mataría el script al cerrarse la app. Se intenta sacarlo del job y, si el job
    # no lo permite, se lanza normalmente.
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    try:
        subprocess.Popen(command, cwd=cwd, env=env, creationflags=flags | breakaway, close_fds=True)
    except OSError:
        subprocess.Popen(command, cwd=cwd, env=env, creationflags=flags, close_fds=True)
